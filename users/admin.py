from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils.html import format_html


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


class LearningLogUserAdmin(UserAdmin):
    """让用户管理列表更适合日常运营和排查。"""

    list_display = (
        'account_overview',
        'email_link',
        'account_status',
        'content_stats',
        'date_joined',
        'last_login_display',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined', 'last_login')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login', 'topic_count', 'entry_count')
    list_per_page = 20
    change_list_template = 'admin/auth/user/change_list.html'
    change_form_template = 'admin/auth/user/change_form.html'
    empty_value_display = '—'

    fieldsets = (
        ('账号信息', {'fields': ('username', 'password')}),
        ('个人资料', {'fields': ('first_name', 'last_name', 'email')}),
        ('学习数据', {'fields': ('topic_count', 'entry_count')}),
        (
            '权限设置',
            {
                'classes': ('collapse',),
                'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            },
        ),
        ('登录时间', {'classes': ('collapse',), 'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (
            '新建用户',
            {
                'classes': ('wide',),
                'fields': ('username', 'email', 'password1', 'password2', 'is_active', 'is_staff'),
            },
        ),
    )

    actions = ('mark_active', 'mark_inactive')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _topic_count=Count('topic', distinct=True),
            _entry_count=Count('topic__entry', distinct=True),
        )

    @admin.display(description='主题数', ordering='_topic_count')
    def topic_count(self, obj):
        return getattr(obj, '_topic_count', 0)

    @admin.display(description='笔记数', ordering='_entry_count')
    def entry_count(self, obj):
        return getattr(obj, '_entry_count', 0)

    @admin.display(description='账号', ordering='username')
    def account_overview(self, obj):
        full_name = obj.get_full_name().strip() or '未填写姓名'
        return format_html(
            '<div class="user-admin-card">'
            '<strong class="user-admin-name">{}</strong>'
            '<span class="user-admin-subline">{}</span>'
            '</div>',
            obj.username,
            full_name,
        )

    @admin.display(description='邮箱', ordering='email')
    def email_link(self, obj):
        if not obj.email:
            return '—'
        return format_html(
            '<a class="user-admin-email" href="mailto:{}">{}</a>',
            obj.email,
            obj.email,
        )

    @admin.display(description='账号状态')
    def account_status(self, obj):
        role = '管理员' if obj.is_superuser else '普通用户'
        active = '已启用' if obj.is_active else '已停用'
        role_class = 'badge-admin' if obj.is_superuser else 'badge-user'
        active_class = 'badge-active' if obj.is_active else 'badge-inactive'
        return format_html(
            '<div class="user-admin-badges">'
            '<span class="user-admin-badge {}">{}</span>'
            '<span class="user-admin-badge {}">{}</span>'
            '</div>',
            role_class,
            role,
            active_class,
            active,
        )

    @admin.display(description='学习数据')
    def content_stats(self, obj):
        return format_html(
            '<div class="user-admin-stats">'
            '<span><strong>{}</strong> 个主题</span>'
            '<span><strong>{}</strong> 条笔记</span>'
            '</div>',
            self.topic_count(obj),
            self.entry_count(obj),
        )

    @admin.display(description='最近登录', ordering='last_login')
    def last_login_display(self, obj):
        if not obj.last_login:
            return '从未登录'
        return obj.last_login.strftime('%Y-%m-%d %H:%M')

    @admin.action(description='将选中用户设为启用')
    def mark_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='将选中用户设为停用')
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)

    class Media:
        css = {'all': ('users/admin-user.css',)}


admin.site.register(User, LearningLogUserAdmin)
admin.site.site_header = '学习笔记后台管理'
admin.site.site_title = '学习笔记后台'
admin.site.index_title = '站点管理'
