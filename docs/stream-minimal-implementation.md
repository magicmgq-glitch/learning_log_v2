# Learning Log v2 Stream Minimal Implementation

本文件用于指导另一模型或后续实现者，按最小风险方式升级 `learning_log_v2`。

目标：

1. 不破坏现有 `Topic / Entry` 主链
2. 先承接低风险流层事件
3. 先让“信息流存在并可读”，再继续扩主题更新和新信号

## 1. 本轮范围

只做：

- `briefing_release`
- `artifact_release`

暂不做：

- `new_signal`
- `theme_update`
- 复杂权限继承
- 独立的流层详情页

## 2. 最小新增模型

新增一个独立模型：

- `StreamItem`

最小字段：

- `event_id`
- `event_type`
- `title`
- `summary`
- `occurred_at`
- `visibility`
- `owner`
- `related_entry`
- `source_object_ids`
- `payload`

设计理由：

- 不改 `Topic / Entry`
- 先让流层和沉淀层通过 `related_entry` 建立跳转桥
- 后续若引入更正式的归档对象，再逐步替换桥接关系

补充规则：

- `owner` 允许为空；为空表示系统发布事件。
- `visibility` 默认公开；信息流展示事件摘要，不等于公开沉淀笔记正文。
- 写入接口仍需要认证，避免匿名写入系统信息流。

## 3. 最小新增接口

### 写入接口

- `POST /api/v1/stream/`

用途：

- 由 `creator-ops-briefing` 写入流层事件

当前只接受：

- `briefing_release`
- `artifact_release`

### 系统读取接口

- `GET /api/v1/stream/`

用途：

- 读取系统流层事件

### 公开读取接口

- `GET /api/v1/public/stream/`

用途：

- 读取可公开展示的流层事件

## 4. 最小新增页面

新增一个公开只读页：

- `/public/stream/`

作用：

- 先验证流层页面存在
- 先展示公开事件卡片
- 复用现有 `Entry` 详情页做跳转

## 5. 最小前端改动

只做两件事：

1. 导航增加“信息流”入口
2. 新增公开信息流列表模板

不要：

- 改首页结构
- 改现有笔记广场逻辑
- 做复杂筛选器

## 6. 最小测试

至少补：

1. 未登录不能写流层事件
2. `briefing_release` 可成功写入
3. 重复 `event_id` 能幂等更新
4. 公开流接口只返回公开事件
5. 公开信息流页面匿名可访问

## 7. 推荐实施顺序

1. 先加模型和迁移
2. 再加 API
3. 再加公开页面
4. 最后补测试

## 8. 通过标准

满足以下条件即可视为第一版完成：

1. `creator-ops-briefing` 可 POST 一条 `briefing_release`
2. `creator-ops-briefing` 可 POST 一条 `artifact_release`
3. 公网页面能看到公开事件
4. 点击事件可跳到对应 `Entry` 详情页
5. 现有 Topic / Entry 页面无行为回归
