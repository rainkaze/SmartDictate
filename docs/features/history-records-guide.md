# 会话库功能说明

会话库用于沉淀 SmartDictate 的完整语音输入结果。用户完成语音识别和文本整理后，系统会把原始转写、整理结果、场景、指标、分类、收藏状态和可选音频附件保存为一条会话记录，方便后续回看、编辑、复用和归档。

## 功能范围

当前会话库支持：

- 自动保存每次整理后的文本会话。
- 在工作台选择“保存音频到会话库”后，将录音、上传文件或 IAT 实时转写音频作为附件归档。
- 按更新时间倒序展示最近会话，收藏记录优先展示。
- 收藏或取消收藏单条会话。
- 按分类筛选会话，支持未分类记录。
- 搜索标题、原始转写和整理结果。
- 新建自定义分类。
- 为单条会话修改分类。
- 编辑会话标题、原始转写、整理结果和输入场景。
- 在会话详情页播放、替换或删除音频附件。
- 将会话详情发送回工作台继续编辑。
- 复制单条会话的整理结果。
- 删除单条会话或清空全部会话。

浏览器 Web Speech API 不提供音频文件，因此该模式只能保存文本会话。

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
audio_path
audio_filename
audio_content_type
audio_size_bytes
audio_duration_ms
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

未分类不是一条真实分类记录，而是 `category_id = null` 的展示状态。删除自定义分类时，关联会话会回到未分类。

## 后端接口

### 获取会话列表

```http
GET /api/transcripts?limit=20&category_id=meeting&favorite=true&query=排期
```

### 更新会话内容和元数据

```http
PATCH /api/transcripts/{transcript_id}
```

请求体示例：

```json
{
  "title": "产品周会纪要",
  "raw_text": "原始转写文本",
  "processed_text": "整理后的文本",
  "scene": "meeting",
  "category_id": "meeting",
  "favorite": true
}
```

### 上传或替换会话音频

```http
POST /api/transcripts/{transcript_id}/audio
```

表单字段：

- `audio`：音频文件。
- `duration_ms`：可选，音频时长，单位毫秒。

### 获取会话音频

```http
GET /api/transcripts/{transcript_id}/audio
```

### 删除会话音频

```http
DELETE /api/transcripts/{transcript_id}/audio
```

### 删除会话和分类

```http
DELETE /api/transcripts/{transcript_id}
DELETE /api/transcripts
GET /api/transcript-categories
POST /api/transcript-categories
PATCH /api/transcript-categories/{category_id}
DELETE /api/transcript-categories/{category_id}
```

删除会话会同步清理对应音频附件。删除自定义分类不会删除会话，只会清空对应会话的 `category_id`。内置分类不可删除。

## 前端交互

前端采用多视图结构：

- 工作台：语音转写、文本整理和是否保存音频的输入选项。
- 会话库：历史会话管理和详情编辑。
- 热词：热词字典维护。
- 设置：本地数据和音频归档说明。

会话库顶部提供搜索、分类筛选、收藏筛选和新建分类。每条会话卡片展示收藏状态、标题、分类、场景、更新时间、字数、是否保存音频和整理结果预览。

打开会话时，前端会进入会话详情区，而不是直接覆盖工作台内容。详情区可以编辑标题、分类、收藏状态、场景、原始转写和整理结果，也可以播放、替换或删除音频附件。用户确认需要继续加工时，可以再把该会话发送回工作台。

## 存储方式

当前版本使用本地 SQLite 数据库保存会话库和分类：

```text
backend/data/smartdictate.sqlite3
```

音频附件保存在：

```text
backend/data/session-audio
```

这些本地数据路径已被 `.gitignore` 忽略，不会提交到仓库。这样可以避免本地演示数据污染代码仓库，同时保持本地优先和可复现的项目定位。
