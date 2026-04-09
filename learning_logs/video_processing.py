import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class VideoProcessingError(Exception):
    pass


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


def remux_uploaded_video(uploaded_file):
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f'input{original_suffix}'
        output_path = tmp_path / 'output.mp4'

        write_upload_to_file(uploaded_file, input_path)

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

        return ContentFile(output_path.read_bytes())


def transcode_uploaded_video(uploaded_file):
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f'input{original_suffix}'
        output_path = tmp_path / 'output.mp4'

        write_upload_to_file(uploaded_file, input_path)

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

        return ContentFile(output_path.read_bytes())


def save_transcoded_video_to_storage(uploaded_file, directory):
    # 1) First try a fast remux (usually much quicker than re-encoding).
    try:
        remuxed_content = remux_uploaded_video(uploaded_file)
        return default_storage.save(f'{directory}/{uuid4().hex}.mp4', remuxed_content)
    except VideoProcessingError:
        pass

    # 2) If remux is not possible, try full re-encoding.
    try:
        transcoded_content = transcode_uploaded_video(uploaded_file)
        return default_storage.save(f'{directory}/{uuid4().hex}.mp4', transcoded_content)
    except VideoProcessingError:
        pass

    # 3) Final fallback: store original to avoid blocking note publishing.
    # This keeps upload usable on low-performance servers.
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'
    return default_storage.save(f'{directory}/{uuid4().hex}{original_suffix}', uploaded_file)


def attach_transcoded_video(entry, uploaded_file):
    if entry.video:
        entry.video.delete(save=False)

    filename = save_transcoded_video_to_storage(uploaded_file, 'videos')
    entry.video.name = filename
    entry.save(update_fields=['video'])
