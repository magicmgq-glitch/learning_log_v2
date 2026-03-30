from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, redirect
from .models import Topic, Entry
from .forms import TopicForm, EntryForm  # 导入我们刚才写的表单

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
        form = EntryForm(data=request.POST)
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
        form = EntryForm(instance=entry, data=request.POST)
        if form.is_valid():
            form.save()
            # 修改成功后，跳回到该主题的详情页去查看最新结果
            return redirect('learning_logs:topic', topic_id=topic.id)

    context = {'entry': entry, 'topic': topic, 'form': form}
    return render(request, 'learning_logs/edit_entry.html', context)