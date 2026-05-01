import json
from functools import wraps
from pathlib import Path
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from users.models import UserAPIToken

from .image_previews import (
    ensure_image_preview,
    media_relative_path_from_url_or_path,
    preview_max_dimension,
    resolve_media_path,
)
from .entry_content import looks_like_html_source
from .models import Entry, StreamItem, Topic
from .upload_limits import (
    document_upload_max_bytes,
    document_upload_max_mb,
    image_upload_max_bytes,
    image_upload_max_mb,
    is_file_too_large,
    video_upload_max_bytes,
    video_upload_max_mb,
)
from .video_processing import (
    attach_video_and_enqueue_transcode,
    save_video_and_enqueue_transcode,
)


VALID_CONTENT_FORMATS = {
    Entry.CONTENT_MARKDOWN,
    Entry.CONTENT_HTML,
}
STREAM_DEFAULT_LIMIT = 50
STREAM_MAX_LIMIT = 100
HTML_SOURCE_ERROR = 'HTML 内容需要提交源码，而不是网页显示后的文字。'


def api_login_required(view_func):
    """Return JSON instead of redirecting when API requests are unauthenticated."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        authorization = request.META.get('HTTP_AUTHORIZATION', '').strip()
        raw_token = ''
        if authorization.lower().startswith('bearer '):
            raw_token = authorization.split(' ', 1)[1].strip()

        authenticator = JWTAuthentication()
        try:
            auth_result = authenticator.authenticate(request)
        except (InvalidToken, TokenError):
            auth_result = None

        if auth_result is not None:
            request.user, request.auth = auth_result
            return view_func(request, *args, **kwargs)

        if raw_token:
            api_token = (
                UserAPIToken.objects.select_related('user')
                .filter(token=raw_token, is_active=True, user__is_active=True)
                .first()
            )
            if api_token is not None:
                api_token.last_used_at = timezone.now()
                api_token.save(update_fields=['last_used_at'])
                request.user = api_token.user
                request.auth = api_token
                return view_func(request, *args, **kwargs)
            return JsonResponse({'error': 'Invalid or expired token.'}, status=401)

        return JsonResponse({'error': 'Authentication required.'}, status=401)

    return wrapped


def build_file_url(request, field_file):
    if not field_file:
        return None
    return request.build_absolute_uri(field_file.url)


def serialize_topic(topic, include_owner=False):
    data = {
        'id': topic.id,
        'text': topic.text,
        'date_added': topic.date_added.isoformat(),
        'is_public': topic.is_public,
    }
    if include_owner:
        data['owner_username'] = topic.owner.username
    return data


def serialize_entry(request, entry, include_owner=False):
    data = {
        'id': entry.id,
        'topic_id': entry.topic_id,
        'topic_text': entry.topic.text,
        'topic_is_public': entry.topic.is_public,
        'text': entry.text,
        'content_format': entry.content_format,
        'date_added': entry.date_added.isoformat(),
        'is_public': entry.is_public,
        'effective_is_public': bool(entry.is_public or entry.topic.is_public),
        'image_url': build_file_url(request, entry.image),
        'video_url': build_file_url(request, entry.video),
        'document_url': build_file_url(request, entry.document),
    }
    if include_owner:
        data['owner_username'] = entry.topic.owner.username
    return data


def build_stream_archive_url(request, item, public_only=False):
    entry = item.related_entry
    if not entry:
        return None

    entry_is_public = bool(entry.is_public or entry.topic.is_public)
    if public_only:
        if not entry_is_public:
            return None
        return request.build_absolute_uri(
            reverse('learning_logs:public_entry_detail', kwargs={'entry_id': entry.id})
        )

    if request.user.is_authenticated and entry.topic.owner_id == request.user.id:
        return request.build_absolute_uri(
            reverse('learning_logs:entry_detail', kwargs={'entry_id': entry.id})
        )
    if entry_is_public:
        return request.build_absolute_uri(
            reverse('learning_logs:public_entry_detail', kwargs={'entry_id': entry.id})
        )
    return None


def serialize_stream_item(request, item, include_owner=False, public_only=False):
    data = {
        'id': item.id,
        'event_id': item.event_id,
        'event_type': item.event_type,
        'display_title': item.title,
        'display_summary': item.summary,
        'occurred_at': item.occurred_at.isoformat(),
        'visibility': item.visibility,
        'source_object_ids': item.source_object_ids,
        'source_links': item.payload.get('source_links', []),
        'related_entry_id': item.related_entry_id,
        'archive_url': build_stream_archive_url(request, item, public_only=public_only),
        'created_at': item.created_at.isoformat(),
        'updated_at': item.updated_at.isoformat(),
    }
    if include_owner:
        data['owner_username'] = item.owner.username if item.owner_id and item.owner else None
        data['actor_type'] = 'user' if item.owner_id else 'system'
    return data


def get_request_data(request):
    if request.content_type and request.content_type.startswith('application/json'):
        try:
            return json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return None
    return request.POST


def get_owned_topic(user, topic_id):
    return Topic.objects.filter(id=topic_id, owner=user).first()


def get_owned_entry(user, entry_id):
    return Entry.objects.filter(id=entry_id, topic__owner=user).select_related('topic').first()


def parse_optional_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'off', ''}:
            return False
    return None


def parse_optional_content_format(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in VALID_CONTENT_FORMATS:
        return normalized
    return None


def apply_entry_updates(entry, data):
    text = data.get('text')
    if text is not None:
        entry.text = text
    content_format = parse_optional_content_format(data.get('content_format'))
    if content_format is not None:
        entry.content_format = content_format
    is_public = parse_optional_bool(data.get('is_public'))
    if is_public is not None:
        entry.is_public = is_public

    if data.get('clear_image'):
        entry.image.delete(save=False)
        entry.image = None

    if data.get('clear_video'):
        entry.video.delete(save=False)
        entry.video = None

    if data.get('clear_document'):
        entry.document.delete(save=False)
        entry.document = None

    entry.save()


def validate_entry_text_for_format(text, content_format):
    if content_format == Entry.CONTENT_HTML and not looks_like_html_source(text):
        return HTML_SOURCE_ERROR
    return None


def parse_iso_datetime_or_none(value):
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = timezone.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def size_error_response(upload, max_bytes, message):
    if is_file_too_large(upload, max_bytes):
        return JsonResponse({'error': message}, status=400)
    return None


def build_stream_item_defaults(data, payload, owner, related_entry):
    occurred_at = parse_iso_datetime_or_none(payload.get('occurred_at')) or timezone.now()
    visibility = (data.get('visibility') or StreamItem.VISIBILITY_PUBLIC).strip().lower()
    owner_value = owner if (data.get('owner_mode') or '').strip().lower() == 'user' else None
    return {
        'event_type': payload.get('item_type'),
        'title': payload.get('display_title'),
        'summary': payload.get('display_summary'),
        'occurred_at': occurred_at,
        'visibility': visibility,
        'owner': owner_value,
        'related_entry': related_entry,
        'source_object_ids': data.get('source_object_ids') or [],
        'payload': payload,
    }


def parse_stream_limit(value):
    try:
        limit = int(value or STREAM_DEFAULT_LIMIT)
    except (TypeError, ValueError):
        return STREAM_DEFAULT_LIMIT
    if limit < 1:
        return STREAM_DEFAULT_LIMIT
    return min(limit, STREAM_MAX_LIMIT)


def apply_stream_cursor(queryset, before_id):
    try:
        cursor_id = int(before_id)
    except (TypeError, ValueError):
        return queryset

    cursor_item = StreamItem.objects.filter(id=cursor_id).only('id', 'occurred_at').first()
    if cursor_item is None:
        return queryset
    return queryset.filter(
        Q(occurred_at__lt=cursor_item.occurred_at)
        | Q(occurred_at=cursor_item.occurred_at, id__lt=cursor_item.id)
    )


def serialize_stream_page(request, stream_items, limit, include_owner=False, public_only=False):
    items = list(stream_items[: limit + 1])
    has_more = len(items) > limit
    visible_items = items[:limit]
    return {
        'stream_items': [
            serialize_stream_item(request, item, include_owner=include_owner, public_only=public_only)
            for item in visible_items
        ],
        'pagination': {
            'limit': limit,
            'has_more': has_more,
            'next_before_id': visible_items[-1].id if has_more and visible_items else None,
        },
    }


@csrf_exempt
@api_login_required
@require_http_methods(['POST'])
def upload_markdown_image(request):
    upload = request.FILES.get('image')
    if not upload:
        return JsonResponse({'error': 'Image file is required.'}, status=400)
    too_large_response = size_error_response(
        upload,
        image_upload_max_bytes(),
        f'Image file exceeds {image_upload_max_mb()}MB limit.',
    )
    if too_large_response:
        return too_large_response

    suffix = Path(upload.name).suffix or '.jpg'
    filename = default_storage.save(f'editor/{uuid4().hex}{suffix}', upload)
    absolute_url = request.build_absolute_uri(default_storage.url(filename))

    return JsonResponse(
        {
            'data': {
                'filePath': absolute_url,
            },
            'url': absolute_url,
        },
        status=201,
    )


@csrf_exempt
@api_login_required
@require_http_methods(['POST'])
def upload_markdown_video(request):
    upload = request.FILES.get('video')
    if not upload:
        return JsonResponse({'error': 'Video file is required.'}, status=400)

    if not (upload.content_type or '').startswith('video/'):
        return JsonResponse({'error': 'Only video files are allowed.'}, status=400)
    too_large_response = size_error_response(
        upload,
        video_upload_max_bytes(),
        f'Video file exceeds {video_upload_max_mb()}MB limit.',
    )
    if too_large_response:
        return too_large_response

    filename = save_video_and_enqueue_transcode(upload, 'editor/videos')

    absolute_url = request.build_absolute_uri(default_storage.url(filename))

    return JsonResponse(
        {
            'data': {
                'filePath': absolute_url,
            },
            'url': absolute_url,
        },
        status=201,
    )


@require_http_methods(['GET'])
def image_preview(request):
    raw_url = request.GET.get('url') or request.GET.get('path')
    size = request.GET.get('size') or 'detail'
    relative_path = media_relative_path_from_url_or_path(raw_url)
    if not relative_path:
        return JsonResponse({'error': 'Valid media image URL is required.'}, status=400)

    preview_relative = ensure_image_preview(relative_path, size=size)
    if not preview_relative:
        return JsonResponse({'error': 'Image preview not found.'}, status=404)

    preview_path = resolve_media_path(preview_relative)
    if not preview_path or not preview_path.exists():
        return JsonResponse({'error': 'Image preview not found.'}, status=404)

    response = FileResponse(preview_path.open('rb'), content_type='image/jpeg')
    response['Cache-Control'] = 'public, max-age=86400'
    response['X-Preview-Max-Dimension'] = str(preview_max_dimension(size))
    return response


@require_http_methods(['GET'])
def public_topic_list(request):
    topics = Topic.objects.filter(is_public=True).select_related('owner').order_by('-date_added')
    return JsonResponse({'topics': [serialize_topic(topic, include_owner=True) for topic in topics]})


@require_http_methods(['GET'])
def public_entry_list(request):
    entries = (
        Entry.objects.filter(Q(is_public=True) | Q(topic__is_public=True))
        .select_related('topic', 'topic__owner')
        .order_by('-date_added')
    )
    return JsonResponse({'entries': [serialize_entry(request, entry, include_owner=True) for entry in entries]})


@require_http_methods(['GET'])
def public_stream_list(request):
    event_type = (request.GET.get('event_type') or '').strip().lower()
    limit = parse_stream_limit(request.GET.get('limit'))
    stream_items = StreamItem.objects.filter(visibility=StreamItem.VISIBILITY_PUBLIC).select_related(
        'owner', 'related_entry', 'related_entry__topic', 'related_entry__topic__owner'
    )
    if event_type:
        stream_items = stream_items.filter(event_type=event_type)
    else:
        stream_items = stream_items.filter(event_type__in=StreamItem.PUBLIC_FEED_EVENT_TYPES)
    stream_items = apply_stream_cursor(stream_items, request.GET.get('before_id'))
    stream_items = stream_items.order_by('-occurred_at', '-id')
    return JsonResponse(serialize_stream_page(request, stream_items, limit, include_owner=True, public_only=True))


@csrf_exempt
@api_login_required
@require_http_methods(['GET', 'POST'])
def stream_list(request):
    if request.method == 'GET':
        event_type = (request.GET.get('event_type') or '').strip().lower()
        limit = parse_stream_limit(request.GET.get('limit'))
        stream_items = StreamItem.objects.all().select_related(
            'owner', 'related_entry', 'related_entry__topic', 'related_entry__topic__owner'
        )
        if event_type:
            stream_items = stream_items.filter(event_type=event_type)
        stream_items = apply_stream_cursor(stream_items, request.GET.get('before_id'))
        stream_items = stream_items.order_by('-occurred_at', '-id')
        return JsonResponse(serialize_stream_page(request, stream_items, limit, public_only=False))

    data = get_request_data(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    output_kind = (data.get('output_kind') or '').strip().lower()
    if output_kind != 'waterfall_item':
        return JsonResponse({'error': 'output_kind must be waterfall_item.'}, status=400)

    payload = data.get('payload')
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'payload must be an object.'}, status=400)

    event_id = (payload.get('item_id') or '').strip()
    event_type = (payload.get('item_type') or '').strip().lower()
    title = (payload.get('display_title') or '').strip()
    summary = (payload.get('display_summary') or '').strip()
    visibility = (data.get('visibility') or '').strip().lower()

    if not event_id:
        return JsonResponse({'error': 'payload.item_id is required.'}, status=400)
    if event_type not in {
        StreamItem.EVENT_BRIEFING_RELEASE,
        StreamItem.EVENT_ARTIFACT_RELEASE,
        StreamItem.EVENT_SIGNAL_ITEM,
        StreamItem.EVENT_THEME_UPDATE,
        StreamItem.EVENT_ACTION_RESULT,
    }:
        return JsonResponse(
            {
                'error': (
                    'item_type must be one of briefing_release, artifact_release, '
                    'signal_item, theme_update, or action_result.'
                )
            },
            status=400,
        )
    if not title:
        return JsonResponse({'error': 'payload.display_title is required.'}, status=400)
    if not summary:
        return JsonResponse({'error': 'payload.display_summary is required.'}, status=400)
    if visibility not in {
        StreamItem.VISIBILITY_PUBLIC,
        StreamItem.VISIBILITY_PRIVATE,
        StreamItem.VISIBILITY_MIXED,
    }:
        return JsonResponse({'error': 'visibility must be public, private, or mixed.'}, status=400)

    source_object_ids = data.get('source_object_ids')
    if not isinstance(source_object_ids, list) or not source_object_ids:
        return JsonResponse({'error': 'source_object_ids must be a non-empty array.'}, status=400)

    related_entry = None
    related_entry_id = payload.get('related_entry_id')
    if related_entry_id is not None:
        related_entry = (
            Entry.objects.filter(id=related_entry_id)
            .select_related('topic', 'topic__owner')
            .first()
        )
        if related_entry is None:
            return JsonResponse({'error': 'related_entry_id points to a missing entry.'}, status=400)
        if related_entry.topic.owner_id != request.user.id:
            return JsonResponse({'error': 'related_entry_id must belong to the current user.'}, status=400)

    defaults = build_stream_item_defaults(data, payload, request.user, related_entry)
    stream_item, created = StreamItem.objects.get_or_create(event_id=event_id, defaults=defaults)

    if not created:
        stream_item.event_type = defaults['event_type']
        stream_item.title = defaults['title']
        stream_item.summary = defaults['summary']
        stream_item.occurred_at = defaults['occurred_at']
        stream_item.visibility = defaults['visibility']
        stream_item.owner = defaults['owner']
        stream_item.related_entry = defaults['related_entry']
        stream_item.source_object_ids = defaults['source_object_ids']
        stream_item.payload = defaults['payload']
        stream_item.save()

    return JsonResponse(
        {'stream_item': serialize_stream_item(request, stream_item, public_only=False)},
        status=201 if created else 200,
    )


@csrf_exempt
@api_login_required
@require_http_methods(['GET', 'POST'])
def topic_list(request):
    if request.method == 'GET':
        topics = Topic.objects.filter(owner=request.user).order_by('date_added')
        return JsonResponse({'topics': [serialize_topic(topic) for topic in topics]})

    data = get_request_data(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    text = (data.get('text') or '').strip()
    if not text:
        return JsonResponse({'error': 'Topic text is required.'}, status=400)

    topic = Topic.objects.create(
        text=text,
        owner=request.user,
        is_public=bool(parse_optional_bool(data.get('is_public'))),
    )
    return JsonResponse({'topic': serialize_topic(topic)}, status=201)


@csrf_exempt
@api_login_required
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def topic_detail(request, topic_id):
    topic = get_owned_topic(request.user, topic_id)
    if topic is None:
        return JsonResponse({'error': 'Topic not found.'}, status=404)

    if request.method == 'GET':
        entries = topic.entry_set.order_by('-date_added')
        return JsonResponse(
            {
                'topic': serialize_topic(topic),
                'entries': [serialize_entry(request, entry) for entry in entries],
            }
        )

    if request.method == 'DELETE':
        topic.delete()
        return JsonResponse({'deleted': True}, status=200)

    data = get_request_data(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    text = data.get('text')
    visibility = parse_optional_bool(data.get('is_public'))
    if request.method == 'PUT':
        if not (text or '').strip():
            return JsonResponse({'error': 'Topic text is required.'}, status=400)
    elif text is None and visibility is None:
        return JsonResponse({'error': 'No fields to update.'}, status=400)

    if text is not None:
        text = text.strip()
        if not text:
            return JsonResponse({'error': 'Topic text cannot be empty.'}, status=400)
        topic.text = text
    if visibility is not None:
        topic.is_public = visibility
    topic.save()

    return JsonResponse({'topic': serialize_topic(topic)})


@csrf_exempt
@api_login_required
@require_http_methods(['GET', 'POST'])
def entry_list(request, topic_id):
    topic = get_owned_topic(request.user, topic_id)
    if topic is None:
        return JsonResponse({'error': 'Topic not found.'}, status=404)

    if request.method == 'GET':
        entries = topic.entry_set.order_by('-date_added')
        return JsonResponse(
            {
                'topic': serialize_topic(topic),
                'entries': [serialize_entry(request, entry) for entry in entries],
            }
        )

    data = get_request_data(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    text = (data.get('text') or '').strip()
    if not text:
        return JsonResponse({'error': 'Entry text is required.'}, status=400)
    raw_text = data.get('text') or ''
    content_format = parse_optional_content_format(data.get('content_format'))
    if data.get('content_format') is not None and content_format is None:
        return JsonResponse({'error': 'Content format must be markdown or html.'}, status=400)
    content_format = content_format or Entry.CONTENT_MARKDOWN
    html_validation_error = validate_entry_text_for_format(raw_text, content_format)
    if html_validation_error:
        return JsonResponse({'error': html_validation_error}, status=400)

    image_upload = request.FILES.get('image')
    video_upload = request.FILES.get('video')
    document_upload = request.FILES.get('document')

    too_large_response = size_error_response(
        image_upload,
        image_upload_max_bytes(),
        f'Image file exceeds {image_upload_max_mb()}MB limit.',
    )
    if too_large_response:
        return too_large_response

    too_large_response = size_error_response(
        video_upload,
        video_upload_max_bytes(),
        f'Video file exceeds {video_upload_max_mb()}MB limit.',
    )
    if too_large_response:
        return too_large_response

    too_large_response = size_error_response(
        document_upload,
        document_upload_max_bytes(),
        f'Document file exceeds {document_upload_max_mb()}MB limit.',
    )
    if too_large_response:
        return too_large_response

    entry = Entry.objects.create(
        topic=topic,
        text=raw_text,
        content_format=content_format,
        is_public=bool(parse_optional_bool(data.get('is_public'))),
        image=image_upload,
        video=None,
        document=document_upload,
    )

    if video_upload:
        try:
            attach_video_and_enqueue_transcode(entry, video_upload)
        except Exception:
            entry.delete()
            return JsonResponse({'error': '视频上传失败，请稍后重试。'}, status=500)

    return JsonResponse({'entry': serialize_entry(request, entry)}, status=201)


@csrf_exempt
@api_login_required
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def entry_detail(request, entry_id):
    entry = get_owned_entry(request.user, entry_id)
    if entry is None:
        return JsonResponse({'error': 'Entry not found.'}, status=404)

    if request.method == 'GET':
        return JsonResponse(
            {
                'topic': serialize_topic(entry.topic),
                'entry': serialize_entry(request, entry),
            }
        )

    if request.method == 'DELETE':
        entry.delete()
        return JsonResponse({'deleted': True}, status=200)

    data = get_request_data(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    text = data.get('text')
    content_format = parse_optional_content_format(data.get('content_format'))
    visibility = parse_optional_bool(data.get('is_public'))
    clear_fields = any(
        data.get(key) for key in ['clear_image', 'clear_video', 'clear_document']
    )
    if data.get('content_format') is not None and content_format is None:
        return JsonResponse({'error': 'Content format must be markdown or html.'}, status=400)

    if request.method == 'PUT':
        if not (text or '').strip():
            return JsonResponse({'error': 'Entry text is required.'}, status=400)
    elif text is None and not clear_fields and visibility is None and content_format is None:
        return JsonResponse({'error': 'No fields to update.'}, status=400)

    if text is not None and not text.strip():
        return JsonResponse({'error': 'Entry text cannot be empty.'}, status=400)

    target_format = content_format or entry.content_format
    target_text = text if text is not None else entry.text
    html_validation_error = validate_entry_text_for_format(target_text, target_format)
    if html_validation_error:
        return JsonResponse({'error': html_validation_error}, status=400)

    apply_entry_updates(entry, data)
    return JsonResponse(
        {
            'topic': serialize_topic(entry.topic),
            'entry': serialize_entry(request, entry),
        }
    )
