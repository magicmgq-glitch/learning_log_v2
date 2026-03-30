from django.urls import path
from . import views

app_name = 'learning_logs'    # 命名空间，非常重要，以后写HTML跳转全靠它

urlpatterns = [
    # 主页路由：空字符串代表主页，交给views.index函数处理，给这个路由起名叫index
    path('', views.index, name='index'),
    # 新增这一行：处理所有主题的页面
    path('topics/', views.topics, name='topics'),
    # 新增这一行：特定主题的详情页
    # <int:topic_id>会捕获URL中的数字，并作为变量传给视图
    path('topics/<int:topic_id>/', views.topic, name='topic'),
    path('new_topic/', views.new_topic, name='new_topic'),
    path('new_entry/<int:topic_id>/', views.new_entry, name='new_entry'),
    path('edit_entry/<int:entry_id>/', views.edit_entry, name='edit_entry'),
    # 专门处理图片无刷新上传的暗门
    path('upload_image/', views.upload_image, name='upload_image'),
    # 修改主题
    path('edit_topic/<int:topic_id>/', views.edit_topic, name='edit_topic'),
    # 删除主题
    path('delete_topic/<int:topic_id>/', views.delete_topic, name='delete_topic'),
    # 删除笔记
    path('delete_entry/<int:entry_id>/', views.delete_entry, name='delete_entry'),
]