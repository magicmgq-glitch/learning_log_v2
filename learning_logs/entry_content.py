import re
from html import escape
from html.parser import HTMLParser

from .models import Entry


UNSAFE_BLOCK_PATTERNS = [
    re.compile(r'<script\b[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<noscript\b[^>]*>.*?</noscript>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<iframe\b[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<object\b[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<embed\b[^>]*>.*?</embed>', re.IGNORECASE | re.DOTALL),
    re.compile(r'<form\b[^>]*>.*?</form>', re.IGNORECASE | re.DOTALL),
]
META_REFRESH_PATTERN = re.compile(
    r'<meta\b[^>]*http-equiv\s*=\s*["\']?refresh["\']?[^>]*>',
    re.IGNORECASE,
)
LINK_TAG_PATTERN = re.compile(r'<link\b[^>]*>', re.IGNORECASE)
BASE_TAG_PATTERN = re.compile(r'<base\b[^>]*>', re.IGNORECASE)
EVENT_HANDLER_PATTERN = re.compile(
    r'\s+on[a-z0-9_-]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)',
    re.IGNORECASE,
)
JAVASCRIPT_PROTOCOL_PATTERN = re.compile(
    r'((?:href|src)\s*=\s*["\'])\s*javascript:[^"\']*(["\'])',
    re.IGNORECASE,
)
STYLE_BLOCK_PATTERN = re.compile(r'<style\b[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL)
BODY_PATTERN = re.compile(r'<body\b[^>]*>(?P<body>.*)</body>', re.IGNORECASE | re.DOTALL)
FULL_DOCUMENT_PATTERN = re.compile(r'<html\b[^>]*>', re.IGNORECASE)
HTML_SOURCE_PATTERN = re.compile(
    r'<!DOCTYPE\s+html|</?[A-Za-z][A-Za-z0-9:_-]*(?:\s[^<>]*)?>',
    re.IGNORECASE,
)


def entry_uses_html(entry):
    return getattr(entry, 'content_format', Entry.CONTENT_MARKDOWN) == Entry.CONTENT_HTML


def normalize_entry_source(raw_text):
    return (raw_text or '').replace('\r\n', '\n').replace('\r', '\n')


def looks_like_html_source(raw_text):
    normalized = normalize_entry_source(raw_text).strip()
    if not normalized:
        return False
    return bool(HTML_SOURCE_PATTERN.search(normalized))


def sanitize_html_source(raw_html):
    cleaned = normalize_entry_source(raw_html).strip()
    for pattern in UNSAFE_BLOCK_PATTERNS:
        cleaned = pattern.sub('', cleaned)
    cleaned = META_REFRESH_PATTERN.sub('', cleaned)
    cleaned = LINK_TAG_PATTERN.sub('', cleaned)
    cleaned = BASE_TAG_PATTERN.sub('', cleaned)
    cleaned = EVENT_HANDLER_PATTERN.sub('', cleaned)
    cleaned = JAVASCRIPT_PROTOCOL_PATTERN.sub(r'\1#\2', cleaned)
    return cleaned.strip()


def extract_html_srcdoc(raw_html):
    safe_html = sanitize_html_source(raw_html)
    if not safe_html:
        return build_html_document('<p>此 HTML 页面暂无内容。</p>')
    if FULL_DOCUMENT_PATTERN.search(safe_html):
        return safe_html
    body = safe_html
    style_blocks = STYLE_BLOCK_PATTERN.findall(safe_html)
    if style_blocks:
        body = STYLE_BLOCK_PATTERN.sub('', safe_html)
    return build_html_document(body, extra_styles='\n'.join(style_blocks))


def build_html_document(body_html, extra_styles=''):
    return (
        '<!DOCTYPE html>'
        '<html lang="zh-CN">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<style>'
        'html,body{margin:0;padding:0;background:#ffffff;color:#111827;}'
        'body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;line-height:1.6;}'
        'img,video{max-width:100%;height:auto;}'
        'table{max-width:100%;}'
        '</style>'
        f'{extra_styles}'
        '</head>'
        f'<body>{body_html}</body>'
        '</html>'
    )


class HTMLPreviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.skip_depth = 0
        self.title = ''
        self.text_chunks = []
        self.first_image = None

    def handle_starttag(self, tag, attrs):
        normalized = tag.lower()
        if normalized in {'script', 'style'}:
            self.skip_depth += 1
            return
        if normalized == 'title':
            self.in_title = True
            return
        if self.skip_depth:
            return
        if normalized == 'img' and self.first_image is None:
            attr_map = dict(attrs)
            src = (attr_map.get('src') or '').strip()
            if src:
                self.first_image = src

    def handle_endtag(self, tag):
        normalized = tag.lower()
        if normalized == 'title':
            self.in_title = False
            return
        if normalized in {'script', 'style'} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = ' '.join(data.split()).strip()
        if not text:
            return
        if self.in_title and not self.title:
            self.title = text
            return
        self.text_chunks.append(text)


def build_html_preview_data(raw_html):
    parser = HTMLPreviewParser()
    parser.feed(sanitize_html_source(raw_html))
    parser.close()

    title = parser.title or (parser.text_chunks[0] if parser.text_chunks else 'HTML 页面笔记')
    remaining = [chunk for chunk in parser.text_chunks if chunk != title]
    body = ' '.join(remaining[:4]).strip() or '这是一篇 HTML 页面笔记。'
    media_kind = 'image' if parser.first_image else None
    media_url = parser.first_image
    return {
        'title': title,
        'body': body,
        'media_kind': media_kind,
        'media_url': media_url,
    }


def build_entry_render_payload(entry):
    if not entry_uses_html(entry):
        return {'content_format': Entry.CONTENT_MARKDOWN, 'html_srcdoc': ''}
    return {
        'content_format': Entry.CONTENT_HTML,
        'html_srcdoc': extract_html_srcdoc(entry.text),
    }


def render_entry_source_for_debug(entry):
    if entry_uses_html(entry):
        return escape(entry.text)
    return entry.text
