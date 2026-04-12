import json
from functools import wraps
from pathlib import Path
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, JsonResponse
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
from .models import Entry, Topic
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


def size_error_response(upload, max_bytes, message):
    if is_file_too_large(upload, max_bytes):
        return JsonResponse({'error': message}, status=400)
    return None


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
