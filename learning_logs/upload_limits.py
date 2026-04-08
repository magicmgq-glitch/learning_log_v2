from django.conf import settings


ONE_MB = 1024 * 1024

DEFAULT_IMAGE_UPLOAD_MAX_BYTES = 5 * ONE_MB
DEFAULT_VIDEO_UPLOAD_MAX_BYTES = 500 * ONE_MB
DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES = 10 * ONE_MB


def image_upload_max_bytes():
    return int(getattr(settings, 'IMAGE_UPLOAD_MAX_BYTES', DEFAULT_IMAGE_UPLOAD_MAX_BYTES))


def video_upload_max_bytes():
    return int(getattr(settings, 'VIDEO_UPLOAD_MAX_BYTES', DEFAULT_VIDEO_UPLOAD_MAX_BYTES))


def document_upload_max_bytes():
    return int(getattr(settings, 'DOCUMENT_UPLOAD_MAX_BYTES', DEFAULT_DOCUMENT_UPLOAD_MAX_BYTES))


def image_upload_max_mb():
    return image_upload_max_bytes() // ONE_MB


def video_upload_max_mb():
    return video_upload_max_bytes() // ONE_MB


def document_upload_max_mb():
    return document_upload_max_bytes() // ONE_MB


def is_file_too_large(upload, max_bytes):
    return bool(upload and upload.size > max_bytes)
