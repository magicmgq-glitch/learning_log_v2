from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from datetime import timedelta

from .models import InviteCode, UserAPIToken


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
        'api_token_status',
        'date_joined',
        'last_login_display',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined', 'last_login')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    readonly_fields = (
        'date_joined',
        'last_login',
        'topic_count',
        'entry_count',
        'api_token_value',
        'api_token_last_used',
        'api_token_actions',
    )
    list_per_page = 20
    change_list_template = 'admin/auth/user/change_list.html'
    change_form_template = 'admin/auth/user/change_form.html'
    empty_value_display = '—'

    fieldsets = (
        ('账号信息', {'fields': ('username', 'password')}),
        ('个人资料', {'fields': ('first_name', 'last_name', 'email')}),
        ('学习数据', {'fields': ('topic_count', 'entry_count')}),
        ('机器人 API', {'fields': ('api_token_value', 'api_token_last_used', 'api_token_actions')}),
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

    actions = ('mark_active', 'mark_inactive', 'regenerate_api_token_for_selected_users')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:user_id>/regenerate-api-token/',
                self.admin_site.admin_view(self.regenerate_api_token_view),
                name='auth_user_regenerate_api_token',
            ),
            path(
                '<int:user_id>/toggle-api-token/',
                self.admin_site.admin_view(self.toggle_api_token_view),
                name='auth_user_toggle_api_token',
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _topic_count=Count('topic', distinct=True),
            _entry_count=Count('topic__entry', distinct=True),
        )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is None:
            return [field for field in readonly_fields if not field.startswith('api_token_')]
        return readonly_fields

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

    @admin.display(description='长期 API Token')
    def api_token_value(self, obj):
        token = UserAPIToken.ensure_for_user(obj)
        return format_html(
            '<div style="max-width:100%; word-break:break-all; font-family:ui-monospace, SFMono-Regular, Menlo, monospace;">'
            '{}'
            '</div>'
            '<div style="margin-top:6px; color:#6b7280;">把这个 Token 提供给 AI 后，可直接使用 '
            '<code>Authorization: Bearer {}</code></div>',
            token.token,
            token.token,
        )

    @admin.display(description='Token 最近使用')
    def api_token_last_used(self, obj):
        token = UserAPIToken.ensure_for_user(obj)
        if not token.last_used_at:
            return '尚未使用'
        return timezone.localtime(token.last_used_at).strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='API Token')
    def api_token_status(self, obj):
        token = UserAPIToken.ensure_for_user(obj)
        status_label = '已启用' if token.is_active else '已停用'
        status_color = '#15803d' if token.is_active else '#6b7280'
        action_label = '停用' if token.is_active else '启用'
        return format_html(
            '<div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">'
            '<span style="color:{}; font-weight:600;">{}</span>'
            '<a class="button" href="{}">{}</a>'
            '</div>',
            status_color,
            status_label,
            reverse('admin:auth_user_toggle_api_token', args=[obj.pk]),
            action_label,
        )

    @admin.display(description='Token 操作')
    def api_token_actions(self, obj):
        token = UserAPIToken.ensure_for_user(obj)
        toggle_label = '停用 API Token' if token.is_active else '启用 API Token'
        return format_html(
            '<div style="display:flex; gap:8px; flex-wrap:wrap;">'
            '<a class="button" href="{}">{}</a>'
            '<a class="button" href="{}">重置 API Token</a>'
            '</div>',
            reverse('admin:auth_user_toggle_api_token', args=[obj.pk]),
            toggle_label,
            reverse('admin:auth_user_regenerate_api_token', args=[obj.pk]),
        )

    def regenerate_api_token_view(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            self.message_user(request, '未找到对应用户。', level=messages.ERROR)
            return redirect(reverse('admin:auth_user_changelist'))

        token = UserAPIToken.ensure_for_user(user)
        token.regenerate()
        self.message_user(request, f'已为用户 {user.username} 重置长期 API Token。', level=messages.SUCCESS)
        return redirect(reverse('admin:auth_user_change', args=[user.pk]))

    def toggle_api_token_view(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            self.message_user(request, '未找到对应用户。', level=messages.ERROR)
            return redirect(reverse('admin:auth_user_changelist'))

        token = UserAPIToken.ensure_for_user(user)
        token.is_active = not token.is_active
        token.save(update_fields=['is_active', 'updated_at'])
        status_label = '启用' if token.is_active else '停用'
        self.message_user(request, f'已将用户 {user.username} 的 API Token 设为{status_label}。', level=messages.SUCCESS)

        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect(reverse('admin:auth_user_change', args=[user.pk]))

    @admin.action(description='将选中用户设为启用')
    def mark_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='将选中用户设为停用')
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description='为选中用户重置长期 API Token')
    def regenerate_api_token_for_selected_users(self, request, queryset):
        count = 0
        for user in queryset:
            token = UserAPIToken.ensure_for_user(user)
            token.regenerate()
            count += 1
        self.message_user(request, f'已重置 {count} 个用户的长期 API Token。', level=messages.SUCCESS)

    class Media:
        css = {'all': ('users/admin-user.css',)}


admin.site.register(User, LearningLogUserAdmin)


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    readonly_fields = ('code',)
    fields = ('code', 'valid_for_days')

    @admin.display(description='当前状态')
    def validity_status(self, obj):
        if obj.is_currently_valid:
            return format_html('<span style="color:#15803d;font-weight:600;">当前有效</span>')
        if obj.is_active and obj.expires_at <= timezone.now():
            return format_html('<span style="color:#b45309;font-weight:600;">已过期</span>')
        return format_html('<span style="color:#6b7280;font-weight:600;">已停用</span>')

    def get_queryset(self, request):
        InviteCode.ensure_current()
        return super().get_queryset(request)

    def changelist_view(self, request, extra_context=None):
        invite = InviteCode.ensure_current()
        return redirect(reverse('admin:users_invitecode_change', args=[invite.pk]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url='', extra_context=None):
        invite = InviteCode.ensure_current()
        if str(object_id) != str(invite.pk):
            return redirect(reverse('admin:users_invitecode_change', args=[invite.pk]))
        extra = extra_context or {}
        extra['title'] = '邀请码设置'
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra)

    def save_model(self, request, obj, form, change):
        obj.expires_at = timezone.now() + timedelta(days=obj.valid_for_days)
        obj.is_active = True
        super().save_model(request, obj, form, change)
        InviteCode.objects.exclude(pk=obj.pk).update(is_active=False)


admin.site.site_header = '学习笔记后台管理'
admin.site.site_title = '学习笔记后台'
admin.site.index_title = '站点管理'
