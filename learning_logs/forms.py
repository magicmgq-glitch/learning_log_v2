from django import forms
from .models import Topic, Entry

class TopicForm(forms.ModelForm):
    """基于 Topic 模型自动生成表单"""
    class Meta:
        model = Topic
        # 告诉 Django，表单里只包含 text 这个字段（因为 date_added 是自动生成的）
        fields = ['text']
        # 不要给输入框加默认的文字标签
        labels = {'text': ''}

class EntryForm(forms.ModelForm):
    """基于 Entry 模型自动生成添加条目的表单"""
    class Meta:
        model = Entry
        fields = ['text']
        labels = {'text': '笔记内容：'}
        # widgets 可以让我们定制 HTML 输入框的样式，这里把文本框加宽到 80 列
        widgets = {'text': forms.Textarea(attrs={'cols': 80})}