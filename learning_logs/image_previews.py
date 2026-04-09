from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from django.conf import settings
from PIL import Image, ImageOps


PREVIEW_DIMENSIONS = {
    'card': 720,
    'detail': 1600,
}

SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif'}


def preview_max_dimension(size):
    return PREVIEW_DIMENSIONS.get(size, PREVIEW_DIMENSIONS['detail'])


def media_relative_path_from_url_or_path(raw_value):
    if not raw_value:
        return None

    parsed = urlparse(raw_value)
    candidate_path = parsed.path if (parsed.scheme or parsed.netloc) else raw_value
    media_url = settings.MEDIA_URL or '/media/'
    if not media_url.startswith('/'):
        media_url = f'/{media_url}'

    if candidate_path.startswith(media_url):
        relative = unquote(candidate_path[len(media_url):]).lstrip('/')
    elif not candidate_path.startswith('/'):
        relative = unquote(candidate_path).lstrip('/')
    else:
        return None

    if not relative:
        return None

    relative_path = PurePosixPath(relative)
    if '..' in relative_path.parts:
        return None

    if relative_path.parts and relative_path.parts[0] == 'previews':
        return None

    if relative_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        return None

    return relative_path.as_posix()


def preview_relative_path(relative_path, size):
    source = PurePosixPath(relative_path)
    suffix = source.suffix.lower().lstrip('.') or 'image'
    filename = f'{source.stem}-{suffix}.jpg'
    return (PurePosixPath('previews') / size / source.parent / filename).as_posix()


def resolve_media_path(relative_path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    candidate = (media_root / PurePosixPath(relative_path)).resolve()

    if candidate != media_root and media_root not in candidate.parents:
        return None

    return candidate


def build_preview_url(request, raw_value, size='detail'):
    relative_path = media_relative_path_from_url_or_path(raw_value)
    if not relative_path:
        return None

    preview_path = ensure_image_preview(relative_path, size=size)
    if not preview_path:
        return None

    media_url = settings.MEDIA_URL if str(settings.MEDIA_URL).endswith('/') else f'{settings.MEDIA_URL}/'
    preview_url = f'{media_url}{preview_path}'
    return request.build_absolute_uri(preview_url)


def ensure_image_preview(relative_path, size='detail'):
    relative_path = media_relative_path_from_url_or_path(relative_path)
    if not relative_path:
        return None

    size = size if size in PREVIEW_DIMENSIONS else 'detail'
    source_path = resolve_media_path(relative_path)
    if not source_path or not source_path.exists() or not source_path.is_file():
        return None

    preview_path = resolve_media_path(preview_relative_path(relative_path, size))
    if not preview_path:
        return None

    preview_path.parent.mkdir(parents=True, exist_ok=True)

    if preview_path.exists() and preview_path.stat().st_mtime >= source_path.stat().st_mtime:
        return preview_relative_path(relative_path, size)

    render_preview(source_path, preview_path, max_dimension=preview_max_dimension(size))
    return preview_relative_path(relative_path, size)


def render_preview(source_path, preview_path, max_dimension):
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel('A'))
            image = background
        elif image.mode == 'P':
            image = image.convert('RGBA')
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel('A'))
            image = background
        else:
            image = image.convert('RGB')

        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=82, optimize=True, progressive=True)
        preview_path.write_bytes(buffer.getvalue())
