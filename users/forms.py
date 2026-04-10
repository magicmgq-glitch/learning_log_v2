from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import InviteCode


class InviteOnlyUserCreationForm(UserCreationForm):
    invite_code = forms.CharField(
        max_length=32,
        label='邀请码',
        help_text='请输入当前有效的邀请码。',
        error_messages={'required': '请填写邀请码'},
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'invite_code', 'password1', 'password2')

    def clean_invite_code(self):
        invite = InviteCode.ensure_current()
        raw_code = (self.cleaned_data.get('invite_code') or '').strip()
        if not raw_code:
            raise forms.ValidationError('请填写邀请码')
        if not invite.is_active or invite.expires_at <= timezone.now() or invite.code != raw_code:
            raise forms.ValidationError('邀请码无效或已过期。')
        self.invite = invite
        return raw_code
