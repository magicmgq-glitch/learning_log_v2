# Learning Log v2 Stream Minimal Implementation

本文件用于指导另一模型或后续实现者，按最小风险方式升级 `learning_log_v2`。

目标：

1. 不破坏现有 `Topic / Entry` 主链
2. 信息流承接系统筛选后的高价值信号，而不是普通发布日志
3. 用分页和默认筛选保护网页与 iOS，支持后续高频写入

## 1. 本轮范围

默认公开信息流只展示：

- `signal_item`：高价值信号
- `theme_update`：高价值主题的持续跟踪
- `action_result`：已经完成的最小落地结果

保留但不默认展示：

- `briefing_release`
- `artifact_release`

原因：

- `briefing_release` 和 `artifact_release` 是发布链路事件，不等于用户需要刷的信息流内容。
- 小红书发布准备包这类内容可以用于端到端测试，但不应该进入默认公开信息流。
- 公开信息流一天可能产生上百条，必须只放“有外部信息价值或推进价值”的条目。

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

## 3. 最小接口

### 写入接口

- `POST /api/v1/stream/`

用途：

- 由 `creator-ops-briefing` 写入流层事件

接受：

- `signal_item`
- `theme_update`
- `action_result`
- `briefing_release`
- `artifact_release`

### 系统读取接口

- `GET /api/v1/stream/`

用途：

- 读取系统流层事件

### 公开读取接口

- `GET /api/v1/public/stream/`

用途：

- 读取默认公开高价值信息流
- 默认排除 `briefing_release` 和 `artifact_release`
- 支持 `limit`，默认 50，最大 100
- 支持 `before_id` 翻页
- 支持 `event_type` 显式查询某一类事件

## 4. 最小新增页面

新增一个公开只读页：

- `/public/stream/`

作用：

- 展示公开高价值信号、主题跟踪和最小落地结果
- 复用现有 `Entry` 详情页做跳转
- 页面默认最多展示 50 条，避免高频信息流拖慢页面

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
2. `briefing_release` 可成功写入但不进默认公开信息流
3. 重复 `event_id` 能幂等更新
4. `signal_item` 可成功写入并进入默认公开信息流
5. 公开流接口只返回公开的默认信息流类型
6. 公开信息流接口支持 `limit` 和 `before_id`
7. 公开信息流页面匿名可访问

## 7. 推荐实施顺序

1. 先加模型和迁移
2. 再加 API
3. 再加公开页面
4. 最后补测试

## 8. 通过标准

满足以下条件即可视为第一版完成：

1. `creator-ops-briefing` 可 POST 一条 `signal_item`
2. `creator-ops-briefing` 可 POST 一条 `theme_update`
3. `creator-ops-briefing` 可 POST 一条 `action_result`
4. 默认公开接口不会显示 `artifact_release`
5. 公开页面最多读取 50 条
6. 点击有公开归档的事件可跳到对应 `Entry` 详情页
7. 现有 Topic / Entry 页面无行为回归
