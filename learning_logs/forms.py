from django import forms
from .models import Topic, Entry
from .entry_content import looks_like_html_source
from .upload_limits import (
    document_upload_max_bytes,
    document_upload_max_mb,
    image_upload_max_bytes,
    image_upload_max_mb,
    is_file_too_large,
    video_upload_max_bytes,
    video_upload_max_mb,
)

class TopicForm(forms.ModelForm):
    """基于 Topic 模型自动生成表单"""
    class Meta:
        model = Topic
        # 告诉 Django，表单里只包含 text 这个字段（因为 date_added 是自动生成的）
        fields = ['text', 'is_public']
        # 不要给输入框加默认的文字标签
        labels = {'text': '', 'is_public': '公开此主题（其他用户可见）'}

class EntryForm(forms.ModelForm):
    """基于 Entry 模型自动生成添加条目的表单"""
    class Meta:
        model = Entry
        fields = ['content_format', 'text', 'is_public', 'image', 'video', 'document']
        labels = {
            'content_format': '内容类型：',
            'text': '笔记内容：',
            'is_public': '公开此笔记（其他用户可见）',
        }
        # widgets 可以让我们定制 HTML 输入框的样式，这里把文本框加宽到 80 列
        widgets = {
            'content_format': forms.Select(),
            'text': forms.Textarea(attrs={'cols': 80, 'rows': 24}),
        }

    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get('text') or ''
        content_format = cleaned_data.get('content_format') or Entry.CONTENT_MARKDOWN
        if content_format == Entry.CONTENT_HTML and text.strip() and not looks_like_html_source(text):
            self.add_error(
                'text',
                'HTML 页面需要粘贴 HTML 源码，而不是浏览器里看到的页面文字。',
            )
        return cleaned_data

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if is_file_too_large(image, image_upload_max_bytes()):
            raise forms.ValidationError(f'图片大小不能超过 {image_upload_max_mb()}MB。')
        return image

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if is_file_too_large(video, video_upload_max_bytes()):
            raise forms.ValidationError(f'视频大小不能超过 {video_upload_max_mb()}MB。')
        return video

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if is_file_too_large(document, document_upload_max_bytes()):
            raise forms.ValidationError(f'附件大小不能超过 {document_upload_max_mb()}MB。')
        return document
