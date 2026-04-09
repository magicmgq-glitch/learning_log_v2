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


def transcode_uploaded_video(uploaded_file):
    original_suffix = Path(uploaded_file.name or '').suffix or '.mp4'

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / f'input{original_suffix}'
        output_path = tmp_path / 'output.mp4'

        with input_path.open('wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

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
            'veryfast',
            '-crf',
            '23',
            '-vf',
            'scale=1280:720:force_original_aspect_ratio=decrease',
            '-c:a',
            'aac',
            '-b:a',
            '128k',
            '-ac',
            '2',
            str(output_path),
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
            stderr = (result.stderr or '').strip().splitlines()
            short_error = stderr[-1] if stderr else 'ffmpeg failed'
            raise VideoProcessingError(f'视频转码失败：{short_error}')

        return ContentFile(output_path.read_bytes())


def save_transcoded_video_to_storage(uploaded_file, directory):
    transcoded_content = transcode_uploaded_video(uploaded_file)
    filename = default_storage.save(f'{directory}/{uuid4().hex}.mp4', transcoded_content)
    return filename


def attach_transcoded_video(entry, uploaded_file):
    if entry.video:
        entry.video.delete(save=False)

    filename = save_transcoded_video_to_storage(uploaded_file, 'videos')
    entry.video.name = filename
    entry.save(update_fields=['video'])
