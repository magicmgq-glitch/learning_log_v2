from django.urls import path

from . import api_views

app_name = 'learning_logs_api'

urlpatterns = [
    path('topics/', api_views.topic_list, name='topic_list'),
    path('topics/<int:topic_id>/', api_views.topic_detail, name='topic_detail'),
    path('topics/<int:topic_id>/entries/', api_views.entry_list, name='entry_list'),
    path('entries/<int:entry_id>/', api_views.entry_detail, name='entry_detail'),
    path('media/image-preview/', api_views.image_preview, name='image_preview'),
    path('uploads/images/', api_views.upload_markdown_image, name='upload_markdown_image'),
    path('uploads/videos/', api_views.upload_markdown_video, name='upload_markdown_video'),
]
