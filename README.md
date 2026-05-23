# SmartDictate

SmartDictate 是一个面向学习、办公和内容创作场景的轻量语音输入助手。项目目标是在不依赖个人服务器的前提下，帮助用户通过浏览器完成语音输入、文本整理、热词纠错和快速复制，提高文本输入效率。

## 选题说明

题目一：语音输入法

本项目没有直接开发系统级输入法驱动，而是实现一个可本地运行的 Web 语音输入产品。这样可以在 72 小时内更好地平衡准确度、易用性、响应速度和成本，并保留后续扩展到桌面端或系统输入法的空间。

## 核心功能

- 浏览器语音识别：使用 Web Speech API 完成低成本实时转写。
- 文本整理：后端提供口癖词清理、空白规整、基础标点和分段处理。
- 热词纠错：支持配置专有名词、课程名、技术词汇等替换规则。
- 输入历史：保存最近的语音输入结果，便于回看和复用。
- 一键复制：快速复制整理后的文本到其他应用。
- 指标展示：展示字数、耗时和输入速度，体现效率提升。

## 技术栈

- Frontend：Vite、HTML、CSS、JavaScript、Web Speech API
- Backend：Python、FastAPI、Pydantic
- Storage：本地 JSON 文件
- Quality：pytest、ruff、EditorConfig

## 目录结构

```text
SmartDictate/
  backend/
    app/
      main.py
      models.py
      services/
        storage.py
        text_processor.py
    data/
      .gitkeep
    tests/
      test_text_processor.py
  frontend/
    src/
      main.js
      styles.css
    index.html
    package.json
    vite.config.js
  docs/
    development-plan.md
  .env.example
  .editorconfig
  .gitignore
  pyproject.toml
  requirements.txt
```

## 环境要求

- Python 3.11 或更高版本
- Node.js 20 LTS 或更高版本
- Chrome 或 Edge 浏览器

浏览器语音识别依赖 Web Speech API。建议使用 Chrome 或 Edge，并通过 `http://127.0.0.1:5173` 访问前端。

## 本地启动

### 1. 后端

推荐使用脚本启动：

```bash
scripts\start-backend.cmd
```

也可以手动从项目根目录启动：

```bash
cd /d D:\Projects\PyCharmProjects\SmartDictate
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### 2. 前端

推荐使用脚本启动：

```bash
scripts\start-frontend.cmd
```

也可以手动启动：

```bash
cd frontend
npm install
npm.cmd run dev
```

访问：

```text
http://127.0.0.1:5173
```

## 质量检查

```bash
python -m pytest
python -m ruff check backend
python -m ruff format backend
cd frontend
npm run build
```

## API

### 健康检查

```http
GET /api/health
```

### 整理文本

```http
POST /api/transcripts/process
Content-Type: application/json

{
  "raw_text": "嗯 我今天想介绍一下七牛云的语音输入法项目",
  "scene": "general"
}
```

### 获取历史

```http
GET /api/transcripts
```

## 工程取舍

- 准确度：MVP 使用浏览器语音识别，后续可接入 faster-whisper 做本地离线识别。
- 易用性：单页完成录音、编辑、整理、复制，不打断输入流程。
- 响应速度：识别在浏览器端实时完成，后端只处理轻量文本规则。
- 成本：无个人服务器依赖，本地即可运行和演示。

## 后续计划

详见 [docs/development-plan.md](docs/development-plan.md)。

## 更多文档

- [后端启动与接口说明](docs/backend-guide.md)
- [文本处理规则说明](docs/text-processing-guide.md)
- [语音输入前端说明](docs/voice-input-guide.md)
- [历史记录功能说明](docs/history-records-guide.md)
