from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import InviteCode


class InviteOnlyRegistrationTests(TestCase):
    def setUp(self):
        self.valid_invite = InviteCode.objects.create(
            expires_at=timezone.now() + timedelta(days=1),
        )

    def test_register_page_shows_invite_code_field(self):
        response = self.client.get(reverse('users:register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '邀请码')

    def test_registration_requires_valid_invite_code(self):
        response = self.client.post(
            reverse('users:register'),
            data={
                'username': 'newbie',
                'invite_code': 'wrong-code',
                'password1': 'VerySecret12345',
                'password2': 'VerySecret12345',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '邀请码无效或已过期')
        self.assertFalse(User.objects.filter(username='newbie').exists())

    def test_registration_requires_invite_code_input(self):
        response = self.client.post(
            reverse('users:register'),
            data={
                'username': 'newbie',
                'invite_code': '',
                'password1': 'VerySecret12345',
                'password2': 'VerySecret12345',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请填写邀请码')
        self.assertFalse(User.objects.filter(username='newbie').exists())

    def test_registration_succeeds_with_active_invite_code(self):
        response = self.client.post(
            reverse('users:register'),
            data={
                'username': 'newbie',
                'invite_code': self.valid_invite.code,
                'password1': 'VerySecret12345',
                'password2': 'VerySecret12345',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newbie').exists())

    def test_expired_invite_code_is_rejected(self):
        expired = InviteCode.objects.create(
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.post(
            reverse('users:register'),
            data={
                'username': 'late-user',
                'invite_code': expired.code,
                'password1': 'VerySecret12345',
                'password2': 'VerySecret12345',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '邀请码无效或已过期')
        self.assertFalse(User.objects.filter(username='late-user').exists())

    def test_ensure_current_rotates_expired_code_and_keeps_duration(self):
        expired = InviteCode.objects.create(
            valid_for_days=7,
            expires_at=timezone.now() - timedelta(minutes=1),
            is_active=True,
        )

        current = InviteCode.ensure_current()

        self.assertEqual(current.id, expired.id)
        self.assertEqual(current.valid_for_days, 7)
        self.assertTrue(current.is_active)
        self.assertGreater(current.expires_at, timezone.now())

    def test_ensure_current_creates_singleton_if_missing(self):
        InviteCode.objects.all().delete()

        current = InviteCode.ensure_current()

        self.assertTrue(current.code)
        self.assertEqual(current.valid_for_days, 1)
        self.assertEqual(InviteCode.objects.count(), 1)
