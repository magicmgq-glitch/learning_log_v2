from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm

# Create your views here.
def register(request):
    """注册新用户"""
    if request.method != 'POST':
        # 如果是 GET 请求，显示一张空的注册表单
        form = UserCreationForm()
    else:
        # 如果是 POST 请求，处理提交的表单数据
        form = UserCreationForm(data=request.POST)

        if form.is_valid():
            # 保存新用户到数据库
            new_user = form.save()

            # 极其贴心的一步：让用户注册后直接自动登录，省去重新输入密码的麻烦
            login(request, new_user)

            # 登录成功后，重定向到主页
            return redirect('learning_logs:index')

    # 如果是 GET 请求或表单填写有误（比如密码太简单），把表单和错误提示发回给页面
    context = {'form': form}
    return render(request, 'registration/register.html', context)