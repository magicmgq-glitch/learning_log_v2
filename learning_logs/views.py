from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, redirect
from .models import Topic, Entry
from .forms import TopicForm, EntryForm  # 导入我们刚才写的表单
from .upload_limits import image_upload_max_bytes, image_upload_max_mb, is_file_too_large

# Create your views here.
def index(request):
    """学习笔记的主页"""
    # 接收到请求后，直接渲染并返回index.html模板
    return render(request, 'learning_logs/index.html')

@login_required
def topics(request):
    """显示所有的主题"""
    # 让Django去数据库把所有的Topic拿出来，并按添加时间升序排列
    topics = Topic.objects.filter(owner=request.user).order_by('date_added')

    # 把查到的数据打包成一个字典context（上下文），准备发给HTML模板
    context = {'topics': topics}
    return render(request, 'learning_logs/topics.html', context)

@login_required
def topic(request, topic_id):
    """显示单个主题及其所有的条目"""
    # 1.根据传过来的ID，去数据库里把那个特定的主题找出来
    topic = Topic.objects.get(id=topic_id)

    # 核心新增：确认请求的主题属于当前用户
    if topic.owner != request.user:
        raise Http404
    # 2.找出该主题关联的所有条目（这就是外键的威力：topic.entry_set）
    # ord_by('-date_added')里面的减号表示“降序”，即最新的条目排在最上面
    entries = topic.entry_set.order_by('-date_added')

    # 3.把主题和条目打包发给HTML
    context = {'topic': topic, 'entries': entries}
    return render(request, 'learning_logs/topic.html', context)

@login_required
def new_topic(request):
    """添加新主题"""
    if request.method != 'POST':
        # 如果不是 POST 请求（说明用户刚打开页面），那就生成一张空白表单
        form = TopicForm()
    else:
        form = TopicForm(data=request.POST)
        if form.is_valid():
            new_topic = form.save(commit=False)

            # 核心修改：将新主题关联到当前自动获取的真实登录用户
            new_topic.owner = request.user

            new_topic.save()
            return redirect('learning_logs:topics')

    context = {'form': form}
    return render(request, 'learning_logs/new_topic.html', context)

@login_required
def new_entry(request, topic_id):
    """在特定的主题中添加新条目"""
    # 先根据传过来的 ID，把对应的主题从数据库里找出来
    topic = Topic.objects.get(id=topic_id)

    # 核心新增：保护新建条目页面
    if topic.owner != request.user:
        raise Http404

    if request.method != 'POST':
        # 未提交数据：创建一个空表单
        form = EntryForm()
    else:
        # POST 提交的数据，对数据进行处理
        form = EntryForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            # commit=False 的意思是：先别急着存进数据库，让我再加点料！
            new_entry = form.save(commit=False)

            # 关键步骤：把刚才查到的 topic 对象，强行赋值给这个新条目的 topic 属性
            # 这就相当于用胶水把它们粘在了一起
            new_entry.topic = topic

            # 绑定好之后，再正式存入数据库
            new_entry.save()

            # 保存成功后，重定向回那个主题的详情页，并带上 topic.id
            return redirect('learning_logs:topic', topic_id=topic.id)

    # 如果是 GET 请求，显示空表单
    context = {'topic': topic, 'form': form}
    return render(request, 'learning_logs/new_entry.html', context)

@login_required
def edit_entry(request, entry_id):
    """编辑既有的条目"""
    # 1. 根据 ID 找到需要修改的那个具体条目
    entry = Entry.objects.get(id=entry_id)
    # 2. 顺藤摸瓜，找到这个条目所属的主题
    topic = entry.topic

    # 核心新增：保护编辑条目页面
    if topic.owner != request.user:
        raise Http404

    if request.method != 'POST':
        # 初次请求：使用当前条目的内容填充表单
        # instance=entry 是核心，它会让网页上的输入框里默认写满你之前敲的旧笔记
        form = EntryForm(instance=entry)
    else:
        # POST 提交的数据：对数据进行处理
        # 这里必须同时传入 instance=entry 和 data=request.POST
        # 意思是：请用用户新提交的 data，去覆盖掉这个 entry 原本的旧数据
        form = EntryForm(instance=entry, data=request.POST, files=request.FILES)
        if form.is_valid():
            form.save()
            # 修改成功后，跳回到该主题的详情页去查看最新结果
            return redirect('learning_logs:topic', topic_id=topic.id)

    context = {'entry': entry, 'topic': topic, 'form': form}
    return render(request, 'learning_logs/edit_entry.html', context)


@login_required
def upload_image(request):
    """
    专门给 Markdown 编辑器提供图片无刷新上传的后端 API 接口。
    只接收 POST 请求中的 image 文件，返回 JSON 格式的图片网址。
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed.'}, status=405)

    upload = request.FILES.get('image')
    if not upload:
        return JsonResponse({'error': 'Image file is required.'}, status=400)
    if is_file_too_large(upload, image_upload_max_bytes()):
        return JsonResponse(
            {'error': f'Image file exceeds {image_upload_max_mb()}MB limit.'},
            status=400,
        )

    # 1. 使用 Django 默认的文件存储系统，把图片存入 media/editor/ 文件夹
    # 这里用了一个 f-string 拼接路径，防止图片名字冲突可以加点时间戳，但目前保持简单
    filename = default_storage.save(f"editor/{upload.name}", upload)

    # 2. 获取这张图片在服务器上的绝对网络地址
    image_url = default_storage.url(filename)

    # 3. 极其关键：按照前端编辑器要求的固定格式，返回 JSON 密码本
    return JsonResponse({
        'data': {
            'filePath': image_url
        }
    })

    # ==========================================
    # V3.0 新增：修改与删除功能
    # ==========================================

@login_required
def edit_topic(request, topic_id):
    """修改主题的名称"""
    topic = Topic.objects.get(id=topic_id)
    # 保护机制：确保只能修改自己的主题
    if topic.owner != request.user:
        raise Http404

    if request.method != 'POST':
        # 初次请求：使用当前主题的内容填充表单
        form = TopicForm(instance=topic)
    else:
        # POST 提交的数据：保存修改
        form = TopicForm(instance=topic, data=request.POST)
        if form.is_valid():
            form.save()
            return redirect('learning_logs:topic', topic_id=topic.id)

    context = {'topic': topic, 'form': form}
    return render(request, 'learning_logs/edit_topic.html', context)

@login_required
def delete_topic(request, topic_id):
    """删除整个主题及其包含的所有笔记"""
    topic = Topic.objects.get(id=topic_id)
    if topic.owner != request.user:
        raise Http404

    # 为了安全，只允许通过 POST 请求进行删除操作
    if request.method == 'POST':
        topic.delete()
        # 删除后回到所有主题列表页
        return redirect('learning_logs:topics')

    return redirect('learning_logs:topic', topic_id=topic.id)

@login_required
def delete_entry(request, entry_id):
    """删除单条笔记"""
    entry = Entry.objects.get(id=entry_id)
    topic = entry.topic
    if topic.owner != request.user:
        raise Http404

    if request.method == 'POST':
        entry.delete()

    # 删除笔记后，留在当前主题页面
    return redirect('learning_logs:topic', topic_id=topic.id)
