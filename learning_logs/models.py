from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Topic(models.Model):
    """用户学习的主题"""
    # 规定主题名称最长200个字符
    text = models.CharField(max_length=200)
    # auto_now_add=True会在创建时自动填入当前时间
    date_added = models.DateTimeField(auto_now_add=True)
    # 核心：将主题与用户绑定。CASCADE意味着如果用户被删除，他所有的主题也会被跟着删除
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    is_public = models.BooleanField(default=False, verbose_name='公开主题')

    def __str__(self):
        """告诉Django，在后台显示这个模型时，直接显示主题的名称"""
        return self.text

class Entry(models.Model):
    """学到的有关某个主题的具体知识（日志条目）"""
    CONTENT_MARKDOWN = 'markdown'
    CONTENT_HTML = 'html'
    CONTENT_FORMAT_CHOICES = [
        (CONTENT_MARKDOWN, 'Markdown 笔记'),
        (CONTENT_HTML, 'HTML 页面'),
    ]

    # 核心：将条目与特定主题绑定（一对多关系）
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    # 使用TextField来存储大段的Markdown文本，不限制长度
    text = models.TextField()
    content_format = models.CharField(
        max_length=20,
        choices=CONTENT_FORMAT_CHOICES,
        default=CONTENT_MARKDOWN,
        verbose_name='内容格式',
    )
    date_added = models.DateTimeField(auto_now_add=True)

    # 新增三大媒体字段
    image = models.ImageField(upload_to='images/', blank=True, null=True, verbose_name='插入图片')
    video = models.FileField(upload_to='videos/', blank=True, null=True, verbose_name='插入视频')
    document = models.FileField(upload_to='documents/', blank=True, null=True, verbose_name='上传附件')
    is_public = models.BooleanField(default=False, verbose_name='公开笔记')

    class Meta:
        """这是一个特殊的内容类，用来告诉Django模型的复数拼写"""
        verbose_name_plural = 'Entries'

    def __str__(self):
        """在后台显示条目时，只显示前50个字符和省略号"""
        if len(self.text) > 50:
            return f"{self.text[:50]}..."
        return self.text


class StreamItem(models.Model):
    """信息流条目，用于承接高频发布事件。"""

    EVENT_BRIEFING_RELEASE = 'briefing_release'
    EVENT_ARTIFACT_RELEASE = 'artifact_release'
    EVENT_TYPE_CHOICES = [
        (EVENT_BRIEFING_RELEASE, '晨报发布'),
        (EVENT_ARTIFACT_RELEASE, '执行结果发布'),
    ]

    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_MIXED = 'mixed'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, '公开'),
        (VISIBILITY_PRIVATE, '私有'),
        (VISIBILITY_MIXED, '混合'),
    ]

    event_id = models.CharField(max_length=120, unique=True)
    event_type = models.CharField(max_length=40, choices=EVENT_TYPE_CHOICES, db_index=True)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    occurred_at = models.DateTimeField(db_index=True)
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PUBLIC,
        db_index=True,
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stream_items',
    )
    related_entry = models.ForeignKey(
        Entry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stream_items',
    )
    source_object_ids = models.JSONField(default=list, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-occurred_at', '-id']
        verbose_name = '信息流条目'
        verbose_name_plural = '信息流条目'

    def __str__(self):
        return f'{self.get_event_type_display()} | {self.title}'
