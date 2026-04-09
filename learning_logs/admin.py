from django.contrib import admin
from django.db.models import Count

from .models import Entry, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('text', 'owner', 'entry_count', 'date_added')
    list_filter = ('date_added', 'owner')
    search_fields = ('text', 'owner__username', 'owner__email')
    autocomplete_fields = ('owner',)
    ordering = ('-date_added',)
    date_hierarchy = 'date_added'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('owner').annotate(_entry_count=Count('entry'))

    @admin.display(description='笔记数', ordering='_entry_count')
    def entry_count(self, obj):
        return getattr(obj, '_entry_count', 0)


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'topic', 'topic_owner', 'has_image', 'has_video', 'has_document', 'date_added')
    list_filter = ('date_added', 'topic__owner')
    search_fields = ('text', 'topic__text', 'topic__owner__username', 'topic__owner__email')
    autocomplete_fields = ('topic',)
    ordering = ('-date_added',)
    date_hierarchy = 'date_added'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('topic', 'topic__owner')

    @admin.display(description='笔记内容')
    def short_text(self, obj):
        text = obj.text.replace('\n', ' ').strip()
        return f'{text[:60]}...' if len(text) > 60 else text

    @admin.display(description='所属用户', ordering='topic__owner__username')
    def topic_owner(self, obj):
        return obj.topic.owner.username

    @admin.display(description='图片', boolean=True)
    def has_image(self, obj):
        return bool(obj.image)

    @admin.display(description='视频', boolean=True)
    def has_video(self, obj):
        return bool(obj.video)

    @admin.display(description='附件', boolean=True)
    def has_document(self, obj):
        return bool(obj.document)
