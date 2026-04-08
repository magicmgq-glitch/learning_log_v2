"""config URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings  # 新增
from django.conf.urls.static import static  # 新增
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.api_views import current_user, register_api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/register/', register_api, name='register_api'),
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/me/', current_user, name='current_user'),
    path(
        'api/v1/',
        include(('learning_logs.api_urls', 'learning_logs_api'), namespace='learning_logs_api'),
    ),
    # 凡是加上了 users/ 前缀的网址，统统交给 users 部门处理
    path('users/', include('users.urls')),
    # 新增下面这行：如果是空路径（主页），就转交给learning_logs的urls处理
    path('', include('learning_logs.urls')),
]

# 新增这段逻辑：允许在本地测试时直接通过网址查看上传的图片和视频
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
