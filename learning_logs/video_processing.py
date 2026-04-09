import subprocess
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from threading import Lock
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


class VideoProcessingError(Exception):
    pass


_TRANSCODE_EXECUTOR = None
_PENDING_TRANSCODE_PATHS = set()
_PENDING_TRANSCODE_LOCK = Lock()


def transcode_worker_count():
    value = int(getattr(settings, 'VIDEO_TRANSCODE_WORKERS', 1))
    return max(value, 1)


def transcode_executor():
    global _TRANSCODE_EXECUTOR
    if _TRANSCODE_EXECUTOR is None:
        _TRANSCODE_EXECUTOR = ThreadPoolExecutor(
            max_workers=transcode_worker_count(),
            thread_name_prefix='video-transcode',
        )
    return _TRANSCODE_EXECUTOR


def ffmpeg_binary():
    return getattr(settings, 'FFMPEG_BINARY', 'ffmpeg')


def ffmpeg_timeout_seconds():
    return int(getattr(settings, 'FFMPEG_TIMEOUT_SECONDS', 420))


def ffmpeg_remux_timeout_seconds():
    return int(getattr(settings, 'FFMPEG_REMUX_TIMEOUT_SECONDS', 120))


def write_upload_to_file(uploaded_file, destination_path):
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    with destination_path.open('wb') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)


def write_storage_to_file(storage_path, destination_path):
    with default_storage.open(storage_path, 'rb') as source, destination_path.open('wb') as destination:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            destination.write(chunk)


def run_ffmpeg(command, timeout_seconds):
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise VideoProcessingError(f'视频处理超时（>{timeout_seconds}秒）。') from error
    except FileNotFoundError as error:
        raise VideoProcessingError('服务器未安装 ffmpeg。') from error
    except OSError as error:
        raise VideoProcessingError(f'服务器视频处理失败：{error}') from error


def remux_video(input_path, output_path):
    command = [
        ffmpeg_binary(),
        '-y',
        '-i',
        str(input_path),
        '-movflags',
        '+faststart',
        '-c',
        'copy',
        str(output_path),
    ]

    result = run_ffmpeg(command, timeout_seconds=ffmpeg_remux_timeout_seconds())
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        stderr = (result.stderr or '').strip().splitlines()
        short_error = stderr[-1] if stderr else 'ffmpeg remux failed'
        raise VideoProcessingError(f'视频快速处理失败：{short_error}')


def transcode_video(input_path, output_path):
    command = [
        ffmpeg_binary(),
        '-y',
        '-i',
        str(input_path),
        '-movflags',
        '+faststart',
        '-pix_fmt',
        'yuv420p',
        '-c:v',
        'libx264',
        '-preset',
        'ultrafast',
        '-crf',
        '28',
        '-vf',
        'scale=960:540:force_original_aspect_ratio=decrease',
        '-c:a',
        'aac',
        '-b:a',
        '96k',
        '-ac',
        '2',
        str(output_path),
    ]

    result = run_ffmpeg(command, timeout_seconds=ffmpeg_timeout_seconds())
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        stderr = (result.stderr or '').strip().splitlines()
        short_error = stderr[-1] if stderr else 'ffmpeg failed'
        raise VideoProcessingError(f'视频转码失败：{short_error}')


def remux_uploaded_video(uploaded_file):
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f'input{original_suffix}'
        output_path = tmp_path / f'output{original_suffix}'
        write_upload_to_file(uploaded_file, input_path)
        remux_video(input_path, output_path)
        return ContentFile(output_path.read_bytes())


def transcode_uploaded_video(uploaded_file):
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f'input{original_suffix}'
        output_path = tmp_path / f'output{original_suffix}'
        write_upload_to_file(uploaded_file, input_path)
        transcode_video(input_path, output_path)
        return ContentFile(output_path.read_bytes())


def save_transcoded_video_to_storage(uploaded_file, directory):
    # 1) First try a fast remux (usually much quicker than re-encoding).
    try:
        remuxed_content = remux_uploaded_video(uploaded_file)
        return default_storage.save(f'{directory}/{uuid4().hex}.mp4', remuxed_content)
    except Exception as error:
        logger.warning('Video remux failed, fallback to transcode: %s', error)

    # 2) If remux is not possible, try full re-encoding.
    try:
        transcoded_content = transcode_uploaded_video(uploaded_file)
        return default_storage.save(f'{directory}/{uuid4().hex}.mp4', transcoded_content)
    except Exception as error:
        logger.warning('Video transcode failed, fallback to original: %s', error)

    # 3) Final fallback: store original to avoid blocking note publishing.
    # This keeps upload usable on low-performance servers.
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'
    return default_storage.save(f'{directory}/{uuid4().hex}{original_suffix}', uploaded_file)


def normalize_storage_path(storage_path):
    path = str(storage_path or '').strip().replace('\\', '/')
    if not path:
        return ''
    return PurePosixPath(path.lstrip('/')).as_posix()


def save_uploaded_video_original(uploaded_file, directory):
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'
    return default_storage.save(f'{directory}/{uuid4().hex}{original_suffix}', uploaded_file)


def replace_storage_file(storage_path, content):
    normalized_path = normalize_storage_path(storage_path)
    if not normalized_path:
        return False

    if default_storage.exists(normalized_path):
        default_storage.delete(normalized_path)
    default_storage.save(normalized_path, content)
    return True


def transcode_storage_video_in_place(storage_path):
    normalized_path = normalize_storage_path(storage_path)
    if not normalized_path or not default_storage.exists(normalized_path):
        return False

    source_suffix = Path(normalized_path).suffix or '.mp4'
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f'source{source_suffix}'
        output_path = tmp_path / f'output{source_suffix}'

        write_storage_to_file(normalized_path, input_path)

        try:
            remux_video(input_path, output_path)
        except Exception as remux_error:
            logger.warning('Storage remux failed for %s, fallback to transcode: %s', normalized_path, remux_error)
            try:
                transcode_video(input_path, output_path)
            except Exception as transcode_error:
                logger.warning('Storage transcode failed for %s, keep original: %s', normalized_path, transcode_error)
                return False

        output_content = ContentFile(output_path.read_bytes())
        return replace_storage_file(normalized_path, output_content)


def _transcode_storage_video_job(storage_path):
    normalized_path = normalize_storage_path(storage_path)
    try:
        transcode_storage_video_in_place(normalized_path)
    except Exception:
        logger.exception('Unexpected video background processing failure: %s', normalized_path)
    finally:
        with _PENDING_TRANSCODE_LOCK:
            _PENDING_TRANSCODE_PATHS.discard(normalized_path)


def enqueue_video_transcode(storage_path):
    normalized_path = normalize_storage_path(storage_path)
    if not normalized_path:
        return False

    with _PENDING_TRANSCODE_LOCK:
        if normalized_path in _PENDING_TRANSCODE_PATHS:
            return False
        _PENDING_TRANSCODE_PATHS.add(normalized_path)

    try:
        transcode_executor().submit(_transcode_storage_video_job, normalized_path)
    except Exception:
        with _PENDING_TRANSCODE_LOCK:
            _PENDING_TRANSCODE_PATHS.discard(normalized_path)
        logger.exception('Failed to enqueue video transcode: %s', normalized_path)
        return False
    return True


def save_video_and_enqueue_transcode(uploaded_file, directory):
    filename = save_uploaded_video_original(uploaded_file, directory)
    enqueue_video_transcode(filename)
    return filename


def attach_video_and_enqueue_transcode(entry, uploaded_file):
    if entry.video:
        entry.video.delete(save=False)
    filename = save_uploaded_video_original(uploaded_file, 'videos')
    entry.video.name = filename
    entry.save(update_fields=['video'])
    enqueue_video_transcode(filename)
    return filename


def attach_transcoded_video(entry, uploaded_file):
    """
    Backward-compatible wrapper:
    keep the old function name but switch to async/background transcode.
    """
    return attach_video_and_enqueue_transcode(entry, uploaded_file)
