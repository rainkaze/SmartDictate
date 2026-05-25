# 会话库功能说明

会话库用于沉淀 SmartDictate 的完整语音输入结果。用户完成语音识别和文本整理后，系统会把原始转写、整理结果、场景、指标和元数据保存为一条会话记录，方便后续回看、收藏、分类、复制和重新打开编辑。

## 功能范围

当前会话库支持：

- 自动保存每次整理后的文本会话。
- 按更新时间倒序展示最近会话，收藏记录优先展示。
- 收藏或取消收藏单条会话。
- 按分类筛选会话，支持未分类记录。
- 搜索标题、原始转写和整理结果。
- 新建自定义分类。
- 为单条会话修改分类。
- 重命名单条会话标题。
- 打开历史会话并回填原始转写、整理结果、输入场景和指标。
- 复制单条会话的整理结果。
- 删除单条会话或清空全部会话。

## 数据模型

会话记录保存在 SQLite 的 `transcripts` 表中：

```text
id
title
raw_text
processed_text
scene
category_id
favorite
metrics_json
created_at
updated_at
```

分类保存在 `transcript_categories` 表中：

```text
id
name
color
sort_order
builtin
created_at
updated_at
```

内置分类包括：

- 会议
- 工作
- 学习
- 灵感
- 代码

未分类不是一条真实分类记录，而是 `category_id = null` 的展示状态。删除自定义分类时，关联会话会回到未分类。

## 后端接口

### 获取会话列表

```http
GET /api/transcripts?limit=20&category_id=meeting&favorite=true&query=排期
```

参数说明：

- `limit`：返回记录数量，最小 1，最大 100，默认 20。
- `category_id`：分类 ID。传 `uncategorized` 时只返回未分类记录。
- `favorite`：是否只返回收藏记录。
- `query`：搜索标题、原始转写和整理结果。

### 更新会话元数据

```http
PATCH /api/transcripts/{transcript_id}
```

请求体示例：

```json
{
  "title": "产品周会纪要",
  "category_id": "meeting",
  "favorite": true
}
```

### 删除单条会话

```http
DELETE /api/transcripts/{transcript_id}
```

### 清空全部会话

```http
DELETE /api/transcripts
```

### 获取分类列表

```http
GET /api/transcript-categories
```

### 新建分类

```http
POST /api/transcript-categories
```

请求体示例：

```json
{
  "name": "面试",
  "color": "#2563eb"
}
```

### 更新分类

```http
PATCH /api/transcript-categories/{category_id}
```

### 删除分类

```http
DELETE /api/transcript-categories/{category_id}
```

内置分类不可删除。删除自定义分类不会删除会话，只会清空对应会话的 `category_id`。

## 前端交互

会话库位于页面右侧。顶部提供：

- 搜索框：按标题和正文搜索。
- 分类筛选：全部分类、未分类和已有分类。
- 收藏筛选：只看收藏。
- 新建分类：输入分类名称并选择颜色。

每条会话卡片展示：

- 收藏状态。
- 会话标题。
- 分类、输入场景、更新时间和字数。
- 整理结果预览。
- 分类选择器。
- 打开、复制、重命名和删除操作。

打开会话时，前端会同时回填原始转写、整理结果、输入场景和指标，便于继续编辑或重新整理。

## 存储方式

当前版本使用本地 SQLite 数据库保存会话库和分类：

```text
backend/data/smartdictate.sqlite3
```

该文件已被 `.gitignore` 忽略，不会提交到仓库。这样可以避免本地演示数据污染代码仓库，同时保持本地优先和可复现的项目定位。
