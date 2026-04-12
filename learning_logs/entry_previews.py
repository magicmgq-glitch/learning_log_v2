import re
from dataclasses import dataclass

from .entry_content import build_html_preview_data, entry_uses_html


IMAGE_PATTERN = re.compile(r'!\[[^\]]*\]\(([^)\s]+)[^)]*\)')
VIDEO_PATTERN = re.compile(r'@\[(?:video|视频)\]\(([^)\s]+)[^)]*\)')
LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]*)\)')
INLINE_CODE_PATTERN = re.compile(r'`([^`]+)`')
HEADING_PATTERN = re.compile(r'^\s{0,3}#{1,6}\s*')
LEADING_LIST_MARKER_PATTERN = re.compile(r'^\s*[-+*]\s+')
LEADING_QUOTE_PATTERN = re.compile(r'^\s*>\s*')
DECORATION_PATTERN = re.compile(r'[*_~#]+')
WHITESPACE_PATTERN = re.compile(r'\s+')


@dataclass
class EntryPreview:
    title: str
    body: str
    media_kind: str | None = None
    media_url: str | None = None
    content_format: str = 'markdown'

    @property
    def has_media(self):
        return bool(self.media_kind and self.media_url)


def build_entry_preview(entry):
    if entry_uses_html(entry):
        preview = build_html_preview_data(entry.text)
        return EntryPreview(
            title=preview['title'],
            body=preview['body'],
            media_kind=preview['media_kind'],
            media_url=preview['media_url'],
            content_format='html',
        )

    text = normalize_text(entry.text)
    title = None
    collected_lines = []
    media_kind = None
    media_url = None
    in_code_fence = False

    for raw_line in text.split('\n'):
        stripped = raw_line.strip()
        marker = code_fence_marker_type(stripped, in_code_fence)
        if marker == 'open':
            in_code_fence = True
            continue
        if marker == 'close':
            in_code_fence = False
            continue
        if not stripped:
            continue

        media = preview_media_from_line(stripped)
        if media and media_kind is None:
            media_kind, media_url = media
            continue

        cleaned = preview_text_line(stripped)
        if not cleaned:
            continue

        if title is None:
            title = cleaned
        else:
            collected_lines.append(cleaned)

    if media_kind is None:
        if entry.image:
            media_kind = 'image'
            media_url = entry.image.url
        elif entry.video:
            media_kind = 'video'
            media_url = entry.video.url

    fallback_title = title or '未命名笔记'
    body = ' '.join(collected_lines).strip() or fallback_title
    return EntryPreview(
        title=fallback_title,
        body=body,
        media_kind=media_kind,
        media_url=media_url,
        content_format='markdown',
    )


def normalize_text(raw_text):
    return raw_text.replace('\r\n', '\n').replace('\r', '\n')


def code_fence_marker_type(line, in_code_fence):
    if not line.startswith('```'):
        return None
    suffix = line[3:]
    if '```' in suffix:
        return None
    if in_code_fence:
        return 'close' if line == '```' else None
    return 'open'


def preview_media_from_line(line):
    image_match = IMAGE_PATTERN.search(line)
    if image_match:
        return 'image', image_match.group(1)

    video_match = VIDEO_PATTERN.search(line)
    if video_match:
        return 'video', video_match.group(1)

    return None


def preview_text_line(line):
    cleaned = HEADING_PATTERN.sub('', line)
    cleaned = LEADING_LIST_MARKER_PATTERN.sub('', cleaned)
    cleaned = LEADING_QUOTE_PATTERN.sub('', cleaned)
    cleaned = IMAGE_PATTERN.sub('', cleaned)
    cleaned = VIDEO_PATTERN.sub('', cleaned)
    cleaned = LINK_PATTERN.sub(r'\1', cleaned)
    cleaned = INLINE_CODE_PATTERN.sub(r'\1', cleaned)
    cleaned = DECORATION_PATTERN.sub(' ', cleaned)
    cleaned = WHITESPACE_PATTERN.sub(' ', cleaned)
    return cleaned.strip()
