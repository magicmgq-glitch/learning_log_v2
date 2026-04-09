from pathlib import Path, PurePosixPath
import re

from django.conf import settings
from django.core.files.storage import default_storage


EMBEDDED_IMAGE_PATTERN = re.compile(r'!\[[^\]]*\]\(([^)\s]+)[^)]*\)')
EMBEDDED_VIDEO_PATTERN = re.compile(r'@\[(?:video|视频)\]\(([^)\s]+)[^)]*\)')


def extract_embedded_media_paths(markdown_text):
    if not markdown_text:
        return set()

    raw_values = EMBEDDED_IMAGE_PATTERN.findall(markdown_text)
    raw_values += EMBEDDED_VIDEO_PATTERN.findall(markdown_text)
    relative_paths = set()

    for raw_value in raw_values:
        relative_path = media_relative_path(raw_value)
        if relative_path:
            relative_paths.add(relative_path)

    return relative_paths


def cleanup_removed_embedded_media(removed_paths, *, exclude_entry_id=None):
    for relative_path in removed_paths:
        if is_path_still_referenced(relative_path, exclude_entry_id=exclude_entry_id):
            continue
        delete_media_with_previews(relative_path)


def media_relative_path(raw_value):
    if not raw_value:
        return None

    media_url = settings.MEDIA_URL or '/media/'
    if not media_url.startswith('/'):
        media_url = f'/{media_url}'

    candidate = raw_value
    if '://' in raw_value:
        media_index = raw_value.find(media_url)
        if media_index == -1:
            return None
        candidate = raw_value[media_index + len(media_url):]
    elif raw_value.startswith(media_url):
        candidate = raw_value[len(media_url):]

    candidate = candidate.lstrip('/')
    if not candidate:
        return None

    relative = PurePosixPath(candidate)
    if '..' in relative.parts:
        return None

    return relative.as_posix()


def is_path_still_referenced(relative_path, *, exclude_entry_id=None):
    from .models import Entry

    lookup_value = relative_path.replace('\\', '/')
    queryset = Entry.objects.filter(text__contains=lookup_value)
    if exclude_entry_id is not None:
        queryset = queryset.exclude(id=exclude_entry_id)
    return queryset.exists()


def delete_media_with_previews(relative_path):
    delete_if_exists(relative_path)

    preview_base = PurePosixPath('previews')
    source = PurePosixPath(relative_path)
    source_suffix = source.suffix.lower().lstrip('.') or 'media'
    preview_filename = f'{source.stem}-{source_suffix}.jpg'

    for size in ('card', 'detail'):
        preview_relative = (preview_base / size / source.parent / preview_filename).as_posix()
        delete_if_exists(preview_relative)


def delete_if_exists(relative_path):
    if default_storage.exists(relative_path):
        default_storage.delete(relative_path)
