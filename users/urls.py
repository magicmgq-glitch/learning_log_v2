from django.urls import path, include
from . import views

app_name = 'users'

urlpatterns = [
    # 我们将在这里直接引入 Django 极其强大的内置身份验证默认 URL
    path('', include('django.contrib.auth.urls')),
    # 核心新增：注册页面的路由
    path('register/', views.register, name='register'),
]