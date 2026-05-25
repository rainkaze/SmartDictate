# SmartDictate

SmartDictate 是一个本地优先的智能语音输入与文本整理工具，面向学习记录、会议纪要、办公写作和内容创作场景。项目通过浏览器或第三方 ASR 服务完成语音转写，再由本地 FastAPI 后端进行文本清洗、热词纠错、分类归档、历史复用和音频留存，帮助用户把口语内容快速整理成可复制、可检索、可再次编辑的文本资产。

## 演示视频

- 百度网盘：[https://pan.baidu.com/s/1KqkVzYQp1p1y6jZQ-WZj9A?pwd=q5gr](https://pan.baidu.com/s/1KqkVzYQp1p1y6jZQ-WZj9A?pwd=q5gr)，提取码：`q5gr`
- 腾讯会议录制：[https://meeting.tencent.com/crm/ldxo6AjPcc](https://meeting.tencent.com/crm/ldxo6AjPcc)

## 选题说明

题目方向：语音输入法。

题目内容：请开发一个语音输入法产品，帮助用户提高文本输入效率。
要求：请了解用户需求并实现输入法开发，能较好地平衡准确度、易用性、响应速度、成本等关键因素。

本项目没有直接开发系统级输入法驱动，而是实现了一个可本地运行的 Web 语音输入产品。这样可以在有限交付周期内完整展示核心闭环：语音采集、语音识别、文本整理、热词纠错、历史归档和复用。相较于系统输入法插件，这个方案更容易部署、演示和验收，也保留了后续扩展到桌面端、浏览器插件或系统输入法的工程接口。

## 核心功能

SmartDictate 的功能围绕“录入、识别、整理、归档、复用”展开，既可以作为课堂或会议场景下的语音输入工具，也可以作为个人知识记录的文本整理工作台。

### 语音输入与识别

- 浏览器实时输入：基于 Web Speech API 调用浏览器原生语音识别能力，适合无第三方密钥的快速演示。
- 第三方 ASR 接入：后端已实现讯飞 IAT、讯飞长语音、百度短语音、百度实时语音等提供商接口，前端可按服务商、来源、语言和识别模式选择。
- 实时流式识别：通过 FastAPI WebSocket 接收前端音频流，支持麦克风或系统音频场景下的边录边转写。
- 本地文件识别：支持上传本地音频文件，由后端统一转交 ASR Provider 处理，适合对已有录音做整理。
- 多语言与模式扩展：抽象了 `zh_cn`、`en_us`、`ja_jp`、方言等语言选项，以及短音频、实时、长音频三类识别模式。

### 文本整理与热词纠错

- 口语清洗：自动移除“嗯、啊、就是”等口癖词，减少语音输入带来的冗余表达。
- 格式整理：规范空白、断句和轻量标点，让识别结果更接近可直接复制的书面文本。
- 场景化处理：支持通用、会议、学习、消息、代码笔记等场景，便于输出不同风格的整理结果。
- 热词替换：内置常用热词规则，并支持用户添加自定义热词，把错误识别词替换为项目名、课程名、人名或技术名词。
- 处理指标：返回原文长度、整理后长度、移除口癖数量和估算阅读时间，便于演示文本整理效果。

### 历史记录与知识管理

- 自动归档：每次整理文本都会保存为历史记录，包含原文、整理结果、场景、指标和创建时间。
- 搜索复用：支持按关键词搜索历史记录，并可一键回填到工作区继续编辑或再次整理。
- 分类管理：支持创建分类、设置颜色、筛选分类，把会议、学习、项目记录分开管理。
- 收藏筛选：重要记录可以标记收藏，便于后续快速定位。
- 会话编辑：支持修改标题、原文、整理结果、场景、分类和收藏状态。
- 音频附件：支持把会话音频保存到历史记录中，并在详情页回放、替换或删除。
- 删除与清空：支持删除单条记录、删除音频附件和清空历史数据。

### 本地存储与交付能力

- 本地 SQLite：历史记录、分类和自定义热词默认保存到 `backend/data/smartdictate.sqlite3`。
- 本地音频目录：上传或保存的会话音频存放在 `backend/data/` 下，便于离线演示和数据隔离。
- 前后端分层：前端专注交互、录音和展示，后端负责 API、ASR Provider、文本处理和持久化。
- 可观测接口：`/api/health` 返回服务状态、版本、存储状态、记录数量和自定义热词数量。
- 交付脚本：提供后端启动、前端启动、后端检查和前端构建脚本，降低演示部署成本。

## 功能闭环

```text
用户语音输入或上传音频
  -> 浏览器或 ASR 服务转写
  -> 后端文本整理
  -> 热词纠错
  -> 输出可复制文本
  -> 保存历史记录与可选音频
  -> 搜索、分类、收藏、回填和复用
```

## 技术栈

### 前端技术

- Vite：负责前端开发服务器和生产构建，启动速度快，适合轻量单页应用。
- 原生 HTML / CSS / JavaScript：不依赖大型 UI 框架，降低安装和运行成本，便于在实训环境快速复现。
- Web Speech API：用于浏览器端实时语音识别，作为无需密钥的基础识别方案。
- Web Audio API：用于麦克风录音、音频采集和流式识别前的音频处理。
- Fetch API：调用后端 REST 接口，完成文本整理、历史记录、热词、分类和音频附件管理。
- WebSocket：连接 `/api/asr/stream`，承载实时语音识别的数据流和识别事件。

### 后端技术

- Python 3.11+：项目后端运行环境，兼顾生态成熟度和类型语法支持。
- FastAPI：提供 REST API、WebSocket、请求校验和自动生成的 OpenAPI 文档。
- Pydantic：定义请求、响应、ASR 结果、历史记录和分类等数据模型。
- Uvicorn：作为 ASGI 服务运行 FastAPI 应用。
- python-multipart：支持音频文件上传表单。
- python-dotenv：从 `.env` 加载数据库、上传目录、CORS 和 ASR 密钥配置。

### 语音识别技术

- 浏览器 Web Speech API：前端直接识别，适合快速演示和无密钥环境。
- 讯飞 IAT：面向实时语音听写场景，适合麦克风或系统音频输入。
- 讯飞长语音：面向录音文件转写场景，适合较长音频材料。
- 百度短语音识别：面向短音频上传识别。
- 百度实时语音识别：面向实时流式识别，通过后端 WebSocket 会话转发音频。
- Provider Registry：后端通过注册表统一管理 ASR 提供商能力、启用状态、语言、来源和模式，方便继续扩展新的识别服务。

### 数据与工程质量

- SQLite：保存历史记录、分类、自定义热词和音频元数据。
- 文件系统存储：保存上传音频和会话音频附件。
- pytest：覆盖后端核心服务和接口行为。
- Ruff：执行 Python 代码风格和静态检查。
- EditorConfig：统一缩进、换行和编码规范。
- Windows CMD 脚本：封装启动和检查命令，方便课堂演示和本地验收。

### 技术分层

```text
浏览器前端
  -> 录音 / 文件选择 / Web Speech API / WebSocket 客户端
  -> FastAPI REST API 与 WebSocket
  -> ASR Provider Registry
  -> 文本处理服务 / 热词服务 / 历史记录服务
  -> SQLite 数据库与本地音频文件
```

## 快速启动

环境要求：

- Python 3.11 或更高版本
- Node.js 20 LTS 或更高版本
- Chrome 或 Edge 浏览器

建议先复制环境变量模板：

```bash
copy .env.example .env
```

启动后端：

```bash
scripts\start-backend.cmd
```

启动前端：

```bash
scripts\start-frontend.cmd
```

访问地址：

```text
前端页面：http://127.0.0.1:5173
接口文档：http://127.0.0.1:8000/docs
健康检查：http://127.0.0.1:8000/api/health
```

如果演示环境不方便出声，可以点击页面中的示例文本按钮，再点击整理文本，验证前后端联动、热词纠错和历史保存。

## 手动启动

后端需要从项目根目录启动：

```bash
cd /d D:\Projects\PyCharmProjects\SmartDictate
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd frontend
npm install
npm.cmd run dev
```

## ASR 配置

项目默认可以使用浏览器能力进行演示。若需要接入第三方语音识别服务，请在 `.env` 中填写对应授权信息。

讯飞配置：

```text
XFYUN_APP_ID=
XFYUN_API_KEY=
XFYUN_API_SECRET=
```

百度配置：

```text
BAIDU_ASR_APP_ID=
BAIDU_ASR_API_KEY=
BAIDU_ASR_SECRET_KEY=
```

其他常用配置：

```text
SMART_DICTATE_DATABASE_FILE=backend/data/smartdictate.sqlite3
SMART_DICTATE_UPLOAD_DIR=backend/data/uploads
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 质量检查

后端测试与静态检查：

```bash
scripts\check-backend.cmd
```

前端生产构建：

```bash
scripts\check-frontend.cmd
```

也可以手动执行：

```bash
python -m pytest
python -m ruff check backend
cd frontend
npm.cmd run build
```

## 项目结构

```text
SmartDictate/
  backend/
    app/
      asr/                 语音识别模型、流式会话和提供商实现
      config/              默认文本处理规则
      core/                后端配置和请求中间件
      services/            文本处理、热词字典、历史记录存储
      main.py              FastAPI 入口与接口路由
      models.py            请求和响应模型
    data/                  本地运行数据，不提交仓库
    tests/                 后端单元测试
  frontend/
    src/
      modules/             API、录音、语音识别和 HTML 工具
      main.js              页面状态和交互逻辑
      styles.css           页面样式
    index.html
  docs/                    中文文档，按 planning / engineering / features / delivery 分组
  scripts/                 本地启动和检查脚本
```

## API 概览

```http
GET    /api/health
GET    /api/asr/providers
WS     /api/asr/stream
POST   /api/asr/transcribe

POST   /api/transcripts/process
GET    /api/transcripts?limit=20
PATCH  /api/transcripts/{transcript_id}
DELETE /api/transcripts/{transcript_id}
DELETE /api/transcripts

POST   /api/transcripts/{transcript_id}/audio
GET    /api/transcripts/{transcript_id}/audio
DELETE /api/transcripts/{transcript_id}/audio

GET    /api/transcript-categories
POST   /api/transcript-categories
PATCH  /api/transcript-categories/{category_id}
DELETE /api/transcript-categories/{category_id}

GET    /api/hotwords
POST   /api/hotwords
DELETE /api/hotwords/{source}
```

完整接口说明可在后端启动后访问 `http://127.0.0.1:8000/docs`。

## 演示建议

1. 启动后端和前端，打开 `http://127.0.0.1:5173`。
2. 先展示健康状态、识别服务选择、语音来源和语言模式。
3. 使用浏览器识别或示例文本生成一段原始转写。
4. 点击整理文本，展示口癖清理、标点整理、热词纠错和阅读时长估算。
5. 添加自定义热词，例如把错误识别词替换为课程名、项目名或技术名词。
6. 再次整理包含该热词的文本，展示热词即时生效。
7. 展示历史记录的搜索、分类、收藏、回填、编辑、复制和删除。
8. 如已保存音频，展示历史会话音频回放与文本复核。
9. 本项目借助 Codex 进行辅助开发，可结合下方说明继续维护、检查和扩展。

## Codex 使用说明

本项目在收尾、修复和功能扩展阶段可以继续使用 Codex 辅助开发。建议在 Codex 中打开项目根目录 `D:\Projects\PyCharmProjects\SmartDictate`，并让 Codex 先阅读相关代码和文档，再执行修改。

适合交给 Codex 的任务：

- 文档维护：检查 README、演示脚本和接口说明是否与代码一致。
- 后端开发：补充 FastAPI 接口、修复 ASR Provider、完善文本处理或历史记录逻辑。
- 前端开发：调整页面交互、修复构建错误、优化录音和历史记录管理体验。
- 测试补充：为热词、文本整理、分类、音频附件等核心功能增加单元测试。
- 质量检查：运行 `scripts\check-backend.cmd`、`scripts\check-frontend.cmd`，并根据报错做最小修复。

推荐提示词：

```text
请先阅读 README.md、backend/app/main.py 和 frontend/src/modules/api-client.js，
检查 README 中的功能描述和 API 列表是否与代码一致，只修改 README。
```

```text
请为热词字典新增一个后端单元测试，完成后运行 pytest，并说明改动文件和测试结果。
```

```text
请检查前端构建失败原因，优先做最小修改，完成后运行 scripts\check-frontend.cmd。
```

## 工程取舍

- 准确度：MVP 可用浏览器识别快速演示，同时接入讯飞和百度 ASR，便于在不同场景下提升识别能力。
- 易用性：核心操作集中在单页应用内，支持语音输入、手动编辑、整理、复制和历史复用。
- 响应速度：实时识别走前端或 WebSocket，文本整理走轻量规则处理，整体响应快。
- 成本：本地运行即可完成核心演示，第三方 ASR 仅在配置授权后启用。
- 隐私：历史记录、自定义热词和音频附件默认保存在本地，不提交到仓库。

## 更多文档

- [文档索引](docs/README.md)
- [开发计划](docs/planning/development-plan.md)
- [系统架构说明](docs/engineering/architecture.md)
- [后端启动与接口说明](docs/engineering/backend-guide.md)
- [持久化与可观测性说明](docs/engineering/persistence-observability.md)
- [Demo 演示脚本](docs/delivery/demo-script.md)
- [交付检查清单](docs/delivery/delivery-checklist.md)
- [语音输入前端说明](docs/features/voice-input-guide.md)
- [文本处理规则说明](docs/features/text-processing-guide.md)
- [热词字典功能说明](docs/features/hotword-dictionary-guide.md)
- [历史记录功能说明](docs/features/history-records-guide.md)
- [百度语音识别说明](docs/features/baidu-asr-guide.md)

## 许可证

本项目采用 [MIT License](https://www.google.com/search?q=LICENSE) 开源协议。
