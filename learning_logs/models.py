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

    def __str__(self):
        """告诉Django，在后台显示这个模型时，直接显示主题的名称"""
        return self.text

class Entry(models.Model):
    """学到的有关某个主题的具体知识（日志条目）"""
    # 核心：将条目与特定主题绑定（一对多关系）
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    # 使用TextField来存储大段的Markdown文本，不限制长度
    text = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        """这是一个特殊的内容类，用来告诉Django模型的复数拼写"""
        verbose_name_plural = 'Entries'

    def __str__(self):
        """在后台显示条目时，只显示前50个字符和省略号"""
        if len(self.text) > 50:
            return f"{self.text[:50]}..."
        return self.text