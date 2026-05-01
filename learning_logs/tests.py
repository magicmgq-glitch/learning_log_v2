import json
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from users.models import UserAPIToken

from .forms import EntryForm
from .models import Entry, StreamItem, Topic


class TopicApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')
        self.other_user = User.objects.create_user(username='bob', password='secret123')

        self.topic = Topic.objects.create(text='Python', owner=self.user)
        self.other_topic = Topic.objects.create(text='Private', owner=self.other_user)
        self.entry = Entry.objects.create(topic=self.topic, text='Learned about views.')

    def test_topic_list_requires_login(self):
        response = self.client.get(reverse('learning_logs_api:topic_list'))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Authentication required.')

    def test_topic_list_returns_only_current_users_topics(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.get(reverse('learning_logs_api:topic_list'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['topics']), 1)
        self.assertEqual(payload['topics'][0]['id'], self.topic.id)
        self.assertEqual(payload['topics'][0]['text'], 'Python')

    def test_topic_detail_returns_topic_and_entries_for_owner(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.get(
            reverse('learning_logs_api:topic_detail', kwargs={'topic_id': self.topic.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['topic']['id'], self.topic.id)
        self.assertEqual(len(payload['entries']), 1)
        self.assertEqual(payload['entries'][0]['id'], self.entry.id)
        self.assertEqual(payload['entries'][0]['text'], 'Learned about views.')

    def test_topic_detail_returns_404_for_other_users_topic(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.get(
            reverse('learning_logs_api:topic_detail', kwargs={'topic_id': self.other_topic.id})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'Topic not found.')

    def test_create_topic_from_json_assigns_current_user(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:topic_list'),
            data=json.dumps({'text': 'Django API'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload['topic']['text'], 'Django API')
        self.assertTrue(Topic.objects.filter(text='Django API', owner=self.user).exists())

    def test_update_topic_with_patch_changes_text(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.patch(
            reverse('learning_logs_api:topic_detail', kwargs={'topic_id': self.topic.id}),
            data=json.dumps({'text': 'Python Advanced'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.text, 'Python Advanced')

    def test_update_topic_with_patch_can_toggle_public(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.patch(
            reverse('learning_logs_api:topic_detail', kwargs={'topic_id': self.topic.id}),
            data=json.dumps({'is_public': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.topic.refresh_from_db()
        self.assertTrue(self.topic.is_public)

    def test_replace_topic_with_put_requires_text(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.put(
            reverse('learning_logs_api:topic_detail', kwargs={'topic_id': self.topic.id}),
            data=json.dumps({}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Topic text is required.')

    def test_delete_topic_removes_owned_topic(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.delete(
            reverse('learning_logs_api:topic_detail', kwargs={'topic_id': self.topic.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Topic.objects.filter(id=self.topic.id).exists())


class EntryApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')
        self.other_user = User.objects.create_user(username='bob', password='secret123')

        self.topic = Topic.objects.create(text='Python', owner=self.user)
        self.other_topic = Topic.objects.create(text='Private', owner=self.other_user)
        self.entry = Entry.objects.create(topic=self.topic, text='Learned about APIs.')
        self.other_entry = Entry.objects.create(topic=self.other_topic, text='Private note.')

    def test_entry_list_requires_login(self):
        response = self.client.get(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id})
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Authentication required.')

    def test_entry_list_returns_entries_for_owned_topic(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.get(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['topic']['id'], self.topic.id)
        self.assertEqual(len(payload['entries']), 1)
        self.assertEqual(payload['entries'][0]['id'], self.entry.id)

    def test_entry_list_returns_404_for_other_users_topic(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.get(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.other_topic.id})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'Topic not found.')

    def test_create_entry_from_json_assigns_topic(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id}),
            data=json.dumps({'text': 'Built the first entry API.'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload['entry']['text'], 'Built the first entry API.')
        self.assertTrue(
            Entry.objects.filter(topic=self.topic, text='Built the first entry API.').exists()
        )

    def test_create_html_entry_from_json_persists_content_format(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id}),
            data=json.dumps(
                {
                    'text': '<!DOCTYPE html><html><body><h1>项目进度表</h1></body></html>',
                    'content_format': 'html',
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload['entry']['content_format'], 'html')
        self.assertTrue(
            Entry.objects.filter(topic=self.topic, content_format='html').exists()
        )

    def test_create_html_entry_rejects_plain_text_page_copy(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id}),
            data=json.dumps(
                {
                    'text': 'mypets 项目进度表 v1 这是页面展示后的文字内容',
                    'content_format': 'html',
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'HTML 内容需要提交源码，而不是网页显示后的文字。')

    @patch('learning_logs.api_views.attach_video_and_enqueue_transcode')
    def test_create_entry_with_video_uses_async_video_pipeline(self, mock_attach_video):
        with tempfile.TemporaryDirectory() as media_dir:
            with self.settings(MEDIA_ROOT=media_dir, MEDIA_URL='/media/'):
                self.client.login(username='alice', password='secret123')

                def fake_attach(entry, uploaded_file):
                    entry.video = 'videos/queued.mov'
                    entry.save(update_fields=['video'])

                mock_attach_video.side_effect = fake_attach

                response = self.client.post(
                    reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id}),
                    data={
                        'text': 'Video note',
                        'video': SimpleUploadedFile('raw.mov', b'video-source', content_type='video/quicktime'),
                    },
                )

                self.assertEqual(response.status_code, 201)
                payload = response.json()
                self.assertIn('/media/videos/', payload['entry']['video_url'])
                self.assertTrue(payload['entry']['video_url'].endswith('.mov'))

    @override_settings(IMAGE_UPLOAD_MAX_BYTES=16)
    def test_create_entry_rejects_oversized_image(self):
        self.client.login(username='alice', password='secret123')
        oversized_image = SimpleUploadedFile(
            'big.jpg',
            b'a' * 17,
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id}),
            data={'text': 'with image', 'image': oversized_image},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Image file exceeds', response.json()['error'])

    def test_entry_detail_returns_owned_entry(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.get(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.entry.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['entry']['id'], self.entry.id)
        self.assertEqual(payload['topic']['id'], self.topic.id)

    def test_entry_detail_returns_404_for_other_users_entry(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.get(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.other_entry.id})
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'Entry not found.')

    def test_update_entry_with_patch_changes_text(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.patch(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.entry.id}),
            data=json.dumps({'text': 'Updated note.'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.text, 'Updated note.')

    def test_update_entry_with_patch_can_switch_to_html_format(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.patch(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.entry.id}),
            data=json.dumps(
                {
                    'text': '<html><body><h1>HTML 笔记</h1></body></html>',
                    'content_format': 'html',
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.content_format, 'html')

    def test_update_entry_to_html_rejects_plain_text_page_copy(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.patch(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.entry.id}),
            data=json.dumps(
                {
                    'text': '项目进度表 这里只是页面上的文字',
                    'content_format': 'html',
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'HTML 内容需要提交源码，而不是网页显示后的文字。')

    def test_create_entry_rejects_invalid_content_format(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:entry_list', kwargs={'topic_id': self.topic.id}),
            data=json.dumps({'text': 'bad', 'content_format': 'richtext'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Content format must be markdown or html.')

    def test_replace_entry_with_put_requires_text(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.put(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.entry.id}),
            data=json.dumps({}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Entry text is required.')

    def test_delete_entry_removes_owned_entry(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.delete(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.entry.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Entry.objects.filter(id=self.entry.id).exists())

    def test_update_entry_with_patch_can_toggle_public(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.patch(
            reverse('learning_logs_api:entry_detail', kwargs={'entry_id': self.entry.id}),
            data=json.dumps({'is_public': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.is_public)

    def test_ai_alias_topic_create_and_entry_create(self):
        self.client.login(username='alice', password='secret123')

        topic_response = self.client.post(
            reverse('learning_logs_api:ai_topic_list'),
            data=json.dumps({'text': 'AI Topic', 'is_public': True}),
            content_type='application/json',
        )
        self.assertEqual(topic_response.status_code, 201)
        topic_id = topic_response.json()['topic']['id']
        self.assertTrue(topic_response.json()['topic']['is_public'])

        entry_response = self.client.post(
            reverse('learning_logs_api:ai_entry_list', kwargs={'topic_id': topic_id}),
            data=json.dumps({'text': 'AI Entry', 'is_public': True}),
            content_type='application/json',
        )
        self.assertEqual(entry_response.status_code, 201)
        self.assertTrue(entry_response.json()['entry']['is_public'])


class JwtAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')
        self.topic = Topic.objects.create(text='Python', owner=self.user)

    def test_token_obtain_pair_returns_access_and_refresh(self):
        response = self.client.post(
            reverse('token_obtain_pair'),
            data={'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('access', payload)
        self.assertIn('refresh', payload)

    def test_token_refresh_returns_new_access_token(self):
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            data={'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )

        response = self.client.post(
            reverse('token_refresh'),
            data={'refresh': token_response.json()['refresh']},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.json())

    def test_current_user_returns_profile_for_bearer_token(self):
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            data={'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )
        access = token_response.json()['access']

        response = self.client.get(
            reverse('current_user'),
            headers={'Authorization': f'Bearer {access}'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['user']['username'], 'alice')

    def test_topic_api_accepts_bearer_token(self):
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            data={'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )
        access = token_response.json()['access']

        response = self.client.get(
            reverse('learning_logs_api:topic_list'),
            headers={'Authorization': f'Bearer {access}'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['topics']), 1)
        self.assertEqual(payload['topics'][0]['text'], 'Python')

    def test_api_rejects_invalid_bearer_token(self):
        response = self.client.get(
            reverse('learning_logs_api:topic_list'),
            headers={'Authorization': 'Bearer invalid-token'},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Invalid or expired token.')

    def test_current_user_returns_profile_for_long_lived_api_token(self):
        api_token = UserAPIToken.ensure_for_user(self.user)
        api_token.is_active = True
        api_token.save(update_fields=['is_active'])

        response = self.client.get(
            reverse('current_user'),
            headers={'Authorization': f'Bearer {api_token.token}'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['username'], 'alice')

    def test_topic_api_accepts_long_lived_api_token(self):
        api_token = UserAPIToken.ensure_for_user(self.user)
        api_token.is_active = True
        api_token.save(update_fields=['is_active'])

        response = self.client.get(
            reverse('learning_logs_api:topic_list'),
            headers={'Authorization': f'Bearer {api_token.token}'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['topics']), 1)
        self.assertEqual(payload['topics'][0]['text'], 'Python')

    def test_long_lived_api_token_updates_last_used_time(self):
        api_token = UserAPIToken.ensure_for_user(self.user)
        api_token.is_active = True
        api_token.save(update_fields=['is_active'])
        self.assertIsNone(api_token.last_used_at)

        response = self.client.get(
            reverse('current_user'),
            headers={'Authorization': f'Bearer {api_token.token}'},
        )

        self.assertEqual(response.status_code, 200)
        api_token.refresh_from_db()
        self.assertIsNotNone(api_token.last_used_at)

    def test_long_lived_api_token_is_disabled_by_default(self):
        api_token = UserAPIToken.ensure_for_user(self.user)

        self.assertFalse(api_token.is_active)

    def test_inactive_long_lived_api_token_is_rejected(self):
        api_token = UserAPIToken.ensure_for_user(self.user)
        api_token.is_active = False
        api_token.save(update_fields=['is_active'])

        response = self.client.get(
            reverse('learning_logs_api:topic_list'),
            headers={'Authorization': f'Bearer {api_token.token}'},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Invalid or expired token.')

    def test_register_api_creates_user_and_returns_tokens(self):
        response = self.client.post(
            reverse('register_api'),
            data=json.dumps(
                {
                    'username': 'charlie',
                    'password1': 'very-secret-123',
                    'password2': 'very-secret-123',
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload['user']['username'], 'charlie')
        self.assertIn('access', payload['tokens'])
        self.assertIn('refresh', payload['tokens'])
        self.assertTrue(User.objects.filter(username='charlie').exists())

    def test_register_api_allows_json_without_csrf_cookie(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse('register_api'),
            data=json.dumps(
                {
                    'username': 'delta',
                    'password1': 'very-secret-123',
                    'password2': 'very-secret-123',
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)

    def test_topic_create_with_bearer_token_does_not_require_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        token_response = csrf_client.post(
            reverse('token_obtain_pair'),
            data={'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )
        access = token_response.json()['access']

        response = csrf_client.post(
            reverse('learning_logs_api:topic_list'),
            data=json.dumps({'text': 'No CSRF needed'}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {access}'},
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Topic.objects.filter(text='No CSRF needed', owner=self.user).exists())

    def test_upload_markdown_image_with_bearer_token(self):
        with tempfile.TemporaryDirectory() as media_dir:
            with self.settings(MEDIA_ROOT=media_dir, MEDIA_URL='/media/'):
                token_response = self.client.post(
                    reverse('token_obtain_pair'),
                    data={'username': 'alice', 'password': 'secret123'},
                    content_type='application/json',
                )
                access = token_response.json()['access']

                gif_data = (
                    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
                    b'\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
                    b'\x00\x02\x02L\x01\x00;'
                )
                upload = SimpleUploadedFile('inline.gif', gif_data, content_type='image/gif')

                response = self.client.post(
                    reverse('learning_logs_api:upload_markdown_image'),
                    data={'image': upload},
                    headers={'Authorization': f'Bearer {access}'},
                )

                self.assertEqual(response.status_code, 201)
                payload = response.json()
                self.assertIn('data', payload)
                self.assertIn('filePath', payload['data'])
                self.assertTrue(payload['data']['filePath'].startswith('http'))

    @override_settings(IMAGE_UPLOAD_MAX_BYTES=16)
    def test_upload_markdown_image_rejects_oversized_file(self):
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            data={'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )
        access = token_response.json()['access']

        oversized_image = SimpleUploadedFile(
            'big.jpg',
            b'a' * 17,
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('learning_logs_api:upload_markdown_image'),
            data={'image': oversized_image},
            headers={'Authorization': f'Bearer {access}'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Image file exceeds', response.json()['error'])


class EntryFormTests(TestCase):
    def test_html_entry_form_rejects_plain_text_page_copy(self):
        form = EntryForm(
            data={
                'content_format': 'html',
                'text': 'mypets 项目进度表 v1 这是浏览器中显示的页面文字',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'HTML 页面需要粘贴 HTML 源码，而不是浏览器里看到的页面文字。',
            form.errors['text'],
        )


class PublicApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')
        private_topic = Topic.objects.create(text='Private Topic', owner=self.user, is_public=False)
        public_topic = Topic.objects.create(text='Public Topic', owner=self.user, is_public=True)

        Entry.objects.create(topic=private_topic, text='Private entry', is_public=False)
        Entry.objects.create(topic=private_topic, text='Entry-only public', is_public=True)
        Entry.objects.create(topic=public_topic, text='Topic public entry', is_public=False)

    def test_public_topics_returns_only_public_topics(self):
        response = self.client.get(reverse('learning_logs_api:public_topic_list'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['topics']), 1)
        self.assertEqual(payload['topics'][0]['text'], 'Public Topic')
        self.assertIn('owner_username', payload['topics'][0])

    def test_public_entries_returns_entry_public_or_topic_public(self):
        response = self.client.get(reverse('learning_logs_api:public_entry_list'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        texts = {entry['text'] for entry in payload['entries']}
        self.assertIn('Entry-only public', texts)
        self.assertIn('Topic public entry', texts)
        self.assertNotIn('Private entry', texts)


class StreamApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')
        self.other_user = User.objects.create_user(username='bob', password='secret123')
        self.topic = Topic.objects.create(text='AI大师之路', owner=self.user, is_public=True)
        self.public_entry = Entry.objects.create(
            topic=self.topic,
            text='公开晨报详情',
            is_public=True,
        )
        self.private_entry = Entry.objects.create(
            topic=self.topic,
            text='私有执行结果详情',
            is_public=False,
        )

    def build_stream_request(self, **payload_overrides):
        payload = {
            'request_id': 'req-briefing-1',
            'output_kind': 'waterfall_item',
            'source_object_ids': ['briefing:2026-05-01'],
            'generated_at': timezone.now().isoformat(),
            'visibility': 'public',
            'delivery_targets': ['learning_log_stream'],
            'payload': {
                'item_id': 'evt-briefing-2026-05-01',
                'item_type': 'briefing_release',
                'display_title': 'AI 晨报已发布',
                'display_summary': '今天的晨报已经生成，并已同步到公开笔记。',
                'occurred_at': timezone.now().isoformat(),
                'source_links': [{'label': '晨报详情', 'url': 'https://example.com/briefing'}],
                'related_entry_id': self.public_entry.id,
            },
        }
        payload.update({k: v for k, v in payload_overrides.items() if k != 'payload'})
        if 'payload' in payload_overrides:
            payload['payload'].update(payload_overrides['payload'])
        return payload

    def test_stream_create_requires_login(self):
        response = self.client.post(
            reverse('learning_logs_api:stream_list'),
            data=json.dumps(self.build_stream_request()),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Authentication required.')

    def test_stream_create_persists_briefing_release(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:stream_list'),
            data=json.dumps(self.build_stream_request()),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()['stream_item']
        self.assertEqual(payload['event_type'], StreamItem.EVENT_BRIEFING_RELEASE)
        self.assertEqual(payload['related_entry_id'], self.public_entry.id)
        self.assertTrue(
            StreamItem.objects.filter(
                event_id='evt-briefing-2026-05-01',
                owner__isnull=True,
                related_entry=self.public_entry,
            ).exists()
        )

    def test_stream_create_upserts_existing_event(self):
        self.client.login(username='alice', password='secret123')
        self.client.post(
            reverse('learning_logs_api:stream_list'),
            data=json.dumps(self.build_stream_request()),
            content_type='application/json',
        )

        response = self.client.post(
            reverse('learning_logs_api:stream_list'),
            data=json.dumps(
                self.build_stream_request(
                    payload={
                        'display_summary': '晨报摘要已刷新。',
                    }
                )
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(StreamItem.objects.filter(event_id='evt-briefing-2026-05-01').count(), 1)
        stream_item = StreamItem.objects.get(event_id='evt-briefing-2026-05-01')
        self.assertEqual(stream_item.summary, '晨报摘要已刷新。')

    def test_stream_create_accepts_signal_item(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:stream_list'),
            data=json.dumps(
                self.build_stream_request(
                    payload={
                        'item_id': 'signal-2026-05-01-1',
                        'item_type': 'signal_item',
                        'display_title': '高价值信号',
                        'display_summary': '这是一条适合进入公开信息流的信号。',
                        'related_entry_id': None,
                    }
                )
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()['stream_item']
        self.assertEqual(payload['event_type'], StreamItem.EVENT_SIGNAL_ITEM)

    def test_stream_create_rejects_unsupported_event_type(self):
        self.client.login(username='alice', password='secret123')

        response = self.client.post(
            reverse('learning_logs_api:stream_list'),
            data=json.dumps(
                self.build_stream_request(
                    payload={
                        'item_id': 'evt-unknown-1',
                        'item_type': 'unknown_item',
                    }
                )
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('item_type must be one of', response.json()['error'])

    def test_public_stream_list_defaults_to_high_value_feed_items(self):
        StreamItem.objects.create(
            event_id='evt-public-1',
            event_type=StreamItem.EVENT_BRIEFING_RELEASE,
            title='公开晨报',
            summary='对外可见',
            occurred_at=timezone.now(),
            visibility=StreamItem.VISIBILITY_PUBLIC,
            related_entry=self.public_entry,
            source_object_ids=['briefing:public'],
        )
        StreamItem.objects.create(
            event_id='signal-public-1',
            event_type=StreamItem.EVENT_SIGNAL_ITEM,
            title='公开信号',
            summary='对外可见',
            occurred_at=timezone.now(),
            visibility=StreamItem.VISIBILITY_PUBLIC,
            source_object_ids=['signal:public'],
        )

        response = self.client.get(reverse('learning_logs_api:public_stream_list'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        titles = {item['display_title'] for item in payload['stream_items']}
        self.assertIn('公开信号', titles)
        self.assertNotIn('公开晨报', titles)

    def test_public_stream_list_can_filter_release_events_explicitly(self):
        StreamItem.objects.create(
            event_id='evt-public-1',
            event_type=StreamItem.EVENT_BRIEFING_RELEASE,
            title='公开晨报',
            summary='对外可见',
            occurred_at=timezone.now(),
            visibility=StreamItem.VISIBILITY_PUBLIC,
            related_entry=self.public_entry,
            source_object_ids=['briefing:public'],
        )

        response = self.client.get(
            reverse('learning_logs_api:public_stream_list'),
            {'event_type': StreamItem.EVENT_BRIEFING_RELEASE},
        )

        self.assertEqual(response.status_code, 200)
        titles = {item['display_title'] for item in response.json()['stream_items']}
        self.assertIn('公开晨报', titles)

    def test_public_stream_list_enforces_limit_and_before_id_cursor(self):
        older = StreamItem.objects.create(
            event_id='signal-old',
            event_type=StreamItem.EVENT_SIGNAL_ITEM,
            title='旧信号',
            summary='第二页',
            occurred_at=timezone.now() - timezone.timedelta(minutes=2),
            visibility=StreamItem.VISIBILITY_PUBLIC,
            source_object_ids=['signal:old'],
        )
        newer = StreamItem.objects.create(
            event_id='signal-new',
            event_type=StreamItem.EVENT_SIGNAL_ITEM,
            title='新信号',
            summary='第一页',
            occurred_at=timezone.now(),
            visibility=StreamItem.VISIBILITY_PUBLIC,
            source_object_ids=['signal:new'],
        )

        first_page = self.client.get(reverse('learning_logs_api:public_stream_list'), {'limit': '1'})

        self.assertEqual(first_page.status_code, 200)
        first_payload = first_page.json()
        self.assertEqual(len(first_payload['stream_items']), 1)
        self.assertEqual(first_payload['stream_items'][0]['display_title'], '新信号')
        self.assertTrue(first_payload['pagination']['has_more'])
        self.assertEqual(first_payload['pagination']['next_before_id'], newer.id)

        second_page = self.client.get(
            reverse('learning_logs_api:public_stream_list'),
            {'limit': '1', 'before_id': str(newer.id)},
        )

        self.assertEqual(second_page.status_code, 200)
        second_payload = second_page.json()
        self.assertEqual(len(second_payload['stream_items']), 1)
        self.assertEqual(second_payload['stream_items'][0]['display_title'], '旧信号')
        self.assertEqual(second_payload['stream_items'][0]['id'], older.id)

    def test_public_stream_list_caps_limit_at_100(self):
        now = timezone.now()
        StreamItem.objects.bulk_create(
            [
                StreamItem(
                    event_id=f'signal-bulk-{index}',
                    event_type=StreamItem.EVENT_SIGNAL_ITEM,
                    title=f'批量信号 {index}',
                    summary='用于验证信息流最大返回数量。',
                    occurred_at=now - timezone.timedelta(seconds=index),
                    visibility=StreamItem.VISIBILITY_PUBLIC,
                    source_object_ids=[f'signal:bulk:{index}'],
                )
                for index in range(101)
            ]
        )

        response = self.client.get(reverse('learning_logs_api:public_stream_list'), {'limit': '500'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['stream_items']), 100)
        self.assertEqual(payload['pagination']['limit'], 100)
        self.assertTrue(payload['pagination']['has_more'])


class PublicWebViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret123')
        private_topic = Topic.objects.create(text='Private Topic', owner=self.user, is_public=False)
        public_topic = Topic.objects.create(text='Public Topic', owner=self.user, is_public=True)

        self.private_entry = Entry.objects.create(topic=private_topic, text='Private entry', is_public=False)
        self.entry_only_public = Entry.objects.create(topic=private_topic, text='Entry-only public', is_public=True)
        self.topic_public_entry = Entry.objects.create(topic=public_topic, text='Topic public entry', is_public=False)

    def test_public_feed_page_allows_anonymous_access(self):
        response = self.client.get(reverse('learning_logs:public_feed'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '笔记广场')
        self.assertContains(response, 'Entry-only public')
        self.assertContains(response, 'Topic public entry')
        self.assertNotContains(response, 'Private entry')

    def test_public_stream_page_allows_anonymous_access(self):
        StreamItem.objects.create(
            event_id='evt-public-stream-1',
            event_type=StreamItem.EVENT_BRIEFING_RELEASE,
            title='公开晨报发布',
            summary='这是一个可公开浏览的信息流事件。',
            occurred_at=timezone.now(),
            visibility=StreamItem.VISIBILITY_PUBLIC,
            related_entry=self.entry_only_public,
            source_object_ids=['briefing:stream'],
        )
        StreamItem.objects.create(
            event_id='signal-public-stream-1',
            event_type=StreamItem.EVENT_SIGNAL_ITEM,
            title='公开高价值信号',
            summary='这条应该出现在公开信息流里。',
            occurred_at=timezone.now(),
            visibility=StreamItem.VISIBILITY_PUBLIC,
            related_entry=self.entry_only_public,
            source_object_ids=['signal:stream'],
        )
        StreamItem.objects.create(
            event_id='signal-private-stream-1',
            event_type=StreamItem.EVENT_SIGNAL_ITEM,
            title='私有高价值信号',
            summary='私有信号不应该出现在公开信息流里。',
            occurred_at=timezone.now(),
            visibility=StreamItem.VISIBILITY_PRIVATE,
            related_entry=self.private_entry,
            source_object_ids=['signal:private'],
        )

        response = self.client.get(reverse('learning_logs:public_stream'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '信息流')
        self.assertContains(response, '系统发布')
        self.assertContains(response, '公开高价值信号')
        self.assertNotContains(response, '公开晨报发布')
        self.assertNotContains(response, '私有高价值信号')
        self.assertContains(
            response,
            reverse('learning_logs:public_entry_detail', kwargs={'entry_id': self.entry_only_public.id}),
        )

    def test_index_page_shows_latest_public_entries(self):
        response = self.client.get(reverse('learning_logs:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '最新笔记')
        self.assertContains(response, '进入笔记广场')
        self.assertContains(response, 'Entry-only public')
        self.assertContains(response, 'Topic public entry')
        self.assertNotContains(response, 'Private entry')

    def test_public_entry_detail_allows_public_entry(self):
        response = self.client.get(
            reverse('learning_logs:public_entry_detail', kwargs={'entry_id': self.entry_only_public.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entry-only public')

    def test_public_entry_detail_renders_html_note_inside_iframe(self):
        html_entry = Entry.objects.create(
            topic=self.entry_only_public.topic,
            text=(
                '<!DOCTYPE html><html lang="zh-CN"><head><style>'
                '.hero{background:#eef5ff;padding:16px;border-radius:12px;}'
                '</style></head><body><section class="hero"><h1>项目进度表</h1></section></body></html>'
            ),
            content_format='html',
            is_public=True,
        )

        response = self.client.get(
            reverse('learning_logs:public_entry_detail', kwargs={'entry_id': html_entry.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'public-entry-html-srcdoc')
        self.assertContains(response, 'data-srcdoc-id="public-entry-html-srcdoc"')
        self.assertContains(response, 'js-entry-html-host')

    def test_public_entry_detail_rejects_private_entry(self):
        response = self.client.get(
            reverse('learning_logs:public_entry_detail', kwargs={'entry_id': self.private_entry.id})
        )

        self.assertEqual(response.status_code, 404)


class OwnedEntryWebViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='secret123')
        self.other_user = User.objects.create_user(username='other', password='secret123')
        self.topic = Topic.objects.create(text='Python', owner=self.user)
        self.entry = Entry.objects.create(
            topic=self.topic,
            text='# 标题\n\n这是一条用于预览的笔记内容，会在主题页显示卡片。',
        )

    def test_topic_page_links_to_owned_entry_detail(self):
        self.client.login(username='owner', password='secret123')

        response = self.client.get(reverse('learning_logs:topic', kwargs={'topic_id': self.topic.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('learning_logs:entry_detail', kwargs={'entry_id': self.entry.id}),
        )
        self.assertContains(response, '查看详情')

    def test_owned_entry_detail_requires_owner(self):
        self.client.login(username='other', password='secret123')

        response = self.client.get(
            reverse('learning_logs:entry_detail', kwargs={'entry_id': self.entry.id})
        )

        self.assertEqual(response.status_code, 404)

    def test_owned_entry_detail_renders_html_note_in_iframe(self):
        html_entry = Entry.objects.create(
            topic=self.topic,
            text=(
                '<!DOCTYPE html><html lang="zh-CN"><head><style>'
                '.summary-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;}'
                '</style></head><body><h1>项目进度表</h1><div class="summary-grid"><div>已完成</div><div>进行中</div></div></body></html>'
            ),
            content_format='html',
        )
        self.client.login(username='owner', password='secret123')

        response = self.client.get(
            reverse('learning_logs:entry_detail', kwargs={'entry_id': html_entry.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HTML 页面')
        self.assertContains(response, 'entry-html-srcdoc')
        self.assertContains(response, 'data-srcdoc-id="entry-html-srcdoc"')
        self.assertContains(response, 'js-entry-html-host')


class ImagePreviewApiTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_dir.name,
            MEDIA_URL='/media/',
        )
        self.media_override.enable()

        self.user = User.objects.create_user(username='alice', password='secret123')
        self.topic = Topic.objects.create(text='Python', owner=self.user)

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def test_image_preview_returns_resized_jpeg_for_entry_image(self):
        upload = SimpleUploadedFile(
            'note.png',
            self.make_image_bytes(size=(2400, 1800), image_format='PNG'),
            content_type='image/png',
        )
        entry = Entry.objects.create(topic=self.topic, text='with image', image=upload)

        response = self.client.get(
            reverse('learning_logs_api:image_preview'),
            {'url': f'http://testserver{entry.image.url}', 'size': 'card'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        response_body = b''.join(response.streaming_content)

        with Image.open(BytesIO(response_body)) as image:
            self.assertLessEqual(max(image.size), 720)

        preview_file = (
            Path(self.media_dir.name)
            / 'previews'
            / 'card'
            / 'images'
            / 'note-png.jpg'
        )
        self.assertTrue(preview_file.exists())

    def test_image_preview_supports_editor_markdown_images(self):
        editor_dir = Path(self.media_dir.name) / 'editor'
        editor_dir.mkdir(parents=True, exist_ok=True)
        source_path = editor_dir / 'inline.jpg'
        source_path.write_bytes(self.make_image_bytes(size=(1800, 1200), image_format='JPEG'))

        response = self.client.get(
            reverse('learning_logs_api:image_preview'),
            {'url': 'http://testserver/media/editor/inline.jpg', 'size': 'detail'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        response_body = b''.join(response.streaming_content)

        with Image.open(BytesIO(response_body)) as image:
            self.assertLessEqual(max(image.size), 1600)

    def test_image_preview_rejects_non_media_urls(self):
        response = self.client.get(
            reverse('learning_logs_api:image_preview'),
            {'url': 'http://example.com/not-allowed.jpg', 'size': 'card'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Valid media image URL is required.')

    def make_image_bytes(self, size, image_format):
        buffer = BytesIO()
        Image.new('RGB', size, color=(120, 180, 220)).save(buffer, format=image_format)
        return buffer.getvalue()

    @patch('learning_logs.api_views.save_video_and_enqueue_transcode')
    def test_upload_markdown_video_with_bearer_token(self, mock_save_video):
        with tempfile.TemporaryDirectory() as media_dir:
            with self.settings(MEDIA_ROOT=media_dir, MEDIA_URL='/media/'):
                token_response = self.client.post(
                    reverse('token_obtain_pair'),
                    data={'username': 'alice', 'password': 'secret123'},
                    content_type='application/json',
                )
                access = token_response.json()['access']

                mock_save_video.side_effect = self.fake_save_video

                mp4_data = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom'
                upload = SimpleUploadedFile('inline.mp4', mp4_data, content_type='video/mp4')

                response = self.client.post(
                    reverse('learning_logs_api:upload_markdown_video'),
                    data={'video': upload},
                    headers={'Authorization': f'Bearer {access}'},
                )

                self.assertEqual(response.status_code, 201)
                payload = response.json()
                self.assertIn('data', payload)
                self.assertIn('filePath', payload['data'])
                self.assertTrue(payload['data']['filePath'].startswith('http'))
                self.assertTrue(payload['data']['filePath'].endswith('.mp4'))

    @override_settings(VIDEO_UPLOAD_MAX_BYTES=16)
    def test_upload_markdown_video_rejects_oversized_file(self):
        token_response = self.client.post(
            reverse('token_obtain_pair'),
            data={'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )
        access = token_response.json()['access']

        oversized_video = SimpleUploadedFile(
            'big.mp4',
            b'\x00' * 17,
            content_type='video/mp4',
        )

        response = self.client.post(
            reverse('learning_logs_api:upload_markdown_video'),
            data={'video': oversized_video},
            headers={'Authorization': f'Bearer {access}'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Video file exceeds', response.json()['error'])

    def fake_save_video(self, uploaded_file, directory):
        relative_path = f'{directory}/queued.mp4'
        destination = Path(settings.MEDIA_ROOT) / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'queued-video')
        return relative_path


class EmbeddedMediaCleanupTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_dir.name,
            MEDIA_URL='/media/',
        )
        self.media_override.enable()

        self.user = User.objects.create_user(username='alice', password='secret123')
        self.topic = Topic.objects.create(text='Python', owner=self.user)

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def test_delete_entry_removes_unreferenced_embedded_media_files(self):
        image_path = self.create_media_file('editor/test-image.jpg', b'image-data')
        video_path = self.create_media_file('editor/videos/test-video.mp4', b'video-data')
        self.create_media_file('previews/card/editor/test-image-jpg.jpg', b'preview-card')
        self.create_media_file('previews/detail/editor/test-image-jpg.jpg', b'preview-detail')

        entry = Entry.objects.create(
            topic=self.topic,
            text=(
                '![图片](http://testserver/media/editor/test-image.jpg)\n'
                '@[video](http://testserver/media/editor/videos/test-video.mp4)\n'
            ),
        )

        entry.delete()

        self.assertFalse(image_path.exists())
        self.assertFalse(video_path.exists())
        self.assertFalse((Path(self.media_dir.name) / 'previews' / 'card' / 'editor' / 'test-image-jpg.jpg').exists())
        self.assertFalse((Path(self.media_dir.name) / 'previews' / 'detail' / 'editor' / 'test-image-jpg.jpg').exists())

    def test_edit_entry_removes_old_embedded_media_when_no_longer_referenced(self):
        image_path = self.create_media_file('editor/old-image.jpg', b'image-data')

        entry = Entry.objects.create(
            topic=self.topic,
            text='![图片](http://testserver/media/editor/old-image.jpg)\n',
        )

        entry.text = '新的纯文本内容'
        entry.save()

        self.assertFalse(image_path.exists())

    def test_shared_embedded_media_is_not_deleted_while_other_entry_still_references_it(self):
        image_path = self.create_media_file('editor/shared-image.jpg', b'image-data')

        first_entry = Entry.objects.create(
            topic=self.topic,
            text='![图片](http://testserver/media/editor/shared-image.jpg)\n',
        )
        second_entry = Entry.objects.create(
            topic=self.topic,
            text='![图片](http://testserver/media/editor/shared-image.jpg)\n',
        )

        first_entry.delete()
        self.assertTrue(image_path.exists())

        second_entry.delete()
        self.assertFalse(image_path.exists())

    def create_media_file(self, relative_path, content):
        path = Path(self.media_dir.name) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path
