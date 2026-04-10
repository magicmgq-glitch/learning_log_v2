from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from secrets import token_urlsafe
from datetime import timedelta

# Create your models here.


class InviteCode(models.Model):
    VALID_FOR_DAY_CHOICES = (
        (1, '24小时'),
        (7, '7天'),
        (30, '30天'),
    )

    code = models.CharField(max_length=32, unique=True, verbose_name='邀请码')
    valid_for_days = models.PositiveSmallIntegerField(
        default=1,
        choices=VALID_FOR_DAY_CHOICES,
        verbose_name='有效期',
    )
    expires_at = models.DateTimeField(verbose_name='失效时间')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        ordering = ('-created_at',)
        verbose_name = '邀请码'
        verbose_name_plural = '邀请码'

    def __str__(self):
        return self.code

    @property
    def is_currently_valid(self):
        return self.is_active and self.expires_at > timezone.now()

    @property
    def valid_for_label(self):
        return dict(self.VALID_FOR_DAY_CHOICES).get(self.valid_for_days, f'{self.valid_for_days}天')

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=self.valid_for_days)
        super().save(*args, **kwargs)

    @staticmethod
    def generate_code():
        return token_urlsafe(12).replace('-', '').replace('_', '')[:16]

    @classmethod
    def singleton(cls):
        invite = cls.objects.order_by('-updated_at', '-id').first()
        if invite is None:
            invite = cls.objects.create(
                code=cls.generate_code(),
                valid_for_days=1,
                expires_at=timezone.now() + timedelta(days=1),
                is_active=True,
            )
        return invite

    @classmethod
    def ensure_current(cls):
        invite = cls.singleton()
        cls.objects.exclude(pk=invite.pk).update(is_active=False)

        if invite.expires_at <= timezone.now() or not invite.code:
            invite.code = cls.generate_code()
            invite.expires_at = timezone.now() + timedelta(days=invite.valid_for_days)
            invite.is_active = True
            invite.save(update_fields=['code', 'expires_at', 'is_active', 'updated_at'])
        return invite


class UserAPIToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='api_token')
    token = models.CharField(max_length=80, unique=True, verbose_name='长期 API Token')
    is_active = models.BooleanField(default=False, verbose_name='是否启用')
    last_used_at = models.DateTimeField(blank=True, null=True, verbose_name='最近使用时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '用户 API Token'
        verbose_name_plural = '用户 API Token'

    def __str__(self):
        return f'{self.user.username} API Token'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_token():
        return f'll_pat_{token_urlsafe(30)}'

    @classmethod
    def ensure_for_user(cls, user):
        token, created = cls.objects.get_or_create(
            user=user,
            defaults={'token': cls.generate_token(), 'is_active': False},
        )
        if not created and not token.token:
            token.token = cls.generate_token()
            token.save(update_fields=['token', 'updated_at'])
        return token

    def regenerate(self):
        self.token = self.generate_token()
        self.save(update_fields=['token', 'updated_at'])
        return self
