# SmartDictate

SmartDictate 是一个本地优先的语音输入助手，面向学习、办公和内容创作场景。它通过浏览器完成语音转写，再由本地 FastAPI 后端进行文本整理、热词纠错、历史记录保存和复用，帮助用户更快获得可直接复制使用的文本。

## 选题说明

题目一：语音输入法

本项目没有直接开发系统级输入法驱动，而是实现一个可本地运行的 Web 语音输入产品。这个方案更适合 72 小时实训交付：能完整展示“语音输入 -> 文本整理 -> 热词纠错 -> 复制复用”的核心闭环，同时兼顾准确度、易用性、响应速度和成本。

## 核心亮点

- 浏览器语音输入：基于 Web Speech API 实时转写，MVP 阶段无需服务器和第三方 API key。
- 文本整理：后端清理口癖词、规整空白、进行轻量标点处理，并按场景格式化输出。
- 热词字典：支持内置热词和用户自定义热词，适配人名、项目名、课程名和技术词。
- 历史复用：自动保存整理结果，支持回填、复制、删除和清空。
- 本地优先：数据保存在本地 JSON 文件中，便于演示和复现。
- 工程规范：前后端分层、配置化规则、中文文档、单元测试、Ruff 检查和启动脚本。

## 功能闭环

```text
用户语音输入
  -> 浏览器实时转写
  -> 后端文本整理
  -> 热词纠错
  -> 输出可复制文本
  -> 保存历史记录
  -> 回填或复制复用
```

## 技术栈

- 前端：Vite、HTML、CSS、JavaScript、Web Speech API
- 后端：Python、FastAPI、Pydantic
- 存储：本地 JSON 文件
- 质量保障：pytest、Ruff、EditorConfig

## 快速启动

环境要求：

- Python 3.11 或更高版本
- Node.js 20 LTS 或更高版本
- Chrome 或 Edge 浏览器

后端：

```bash
scripts\start-backend.cmd
```

前端：

```bash
scripts\start-frontend.cmd
```

脚本说明：

```text
scripts/start-backend.cmd   启动 FastAPI 后端
scripts/start-frontend.cmd  启动 Vite 前端
scripts/check-backend.cmd   运行后端测试和 Ruff 检查
scripts/check-frontend.cmd  运行前端生产构建
```

访问：

```text
http://127.0.0.1:5173
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

如果不方便出声，可以点击页面里的“填入示例”，再点击“整理文本”验证前后端联动。

## 手动启动

后端必须从项目根目录启动：

```bash
cd /d D:\Projects\PyCharmProjects\SmartDictate
conda activate SmartDictate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd frontend
npm install
npm.cmd run dev
```

## 质量检查

```bash
D:\CodeTools\miniconda\envs\SmartDictate\python.exe -m pytest
D:\CodeTools\miniconda\envs\SmartDictate\python.exe -m ruff check backend
cd frontend
npm.cmd run build
```

也可以使用脚本：

```bash
scripts\check-backend.cmd
scripts\check-frontend.cmd
```

## 项目结构

```text
SmartDictate/
  backend/
    app/
      config/              默认文本规则
      core/                后端配置
      services/            文本处理、热词、历史存储
      main.py              FastAPI 入口
      models.py            请求和响应模型
    data/                  本地运行数据，不提交仓库
    tests/                 后端单元测试
  frontend/
    src/
      modules/             API、语音识别、HTML 工具
      main.js              页面状态和交互逻辑
      styles.css           页面样式
    index.html
  docs/                    中文工程文档
  scripts/                 本地启动和检查脚本
```

## API 概览

```http
GET /api/health
POST /api/transcripts/process
GET /api/transcripts?limit=10
DELETE /api/transcripts/{transcript_id}
DELETE /api/transcripts
GET /api/hotwords
POST /api/hotwords
DELETE /api/hotwords/{source}
```

完整接口可以在后端启动后访问 `http://127.0.0.1:8000/docs`。

## 工程取舍

- 准确度：MVP 使用浏览器语音识别，并通过热词字典提升专有名词准确度；后续可接在线语音识别 API。
- 易用性：核心操作集中在单页中，支持语音输入、手动编辑、整理、复制、历史复用。
- 响应速度：浏览器端实时转写，后端只处理轻量文本规则，响应快。
- 成本：无需个人服务器和付费模型，本地即可运行和演示。
- 隐私：历史记录和自定义热词默认保存在本地文件，不提交仓库。

## 演示建议

推荐演示路径：

1. 启动前后端。
2. 点击“填入示例”，展示安静环境下的演示兜底方案。
3. 点击“整理文本”，展示口癖清理、轻量标点整理和热词纠错。
4. 添加自定义热词，例如 `小七 -> 七牛云助手`。
5. 再次整理包含“小七”的文本，展示热词即时生效。
6. 展示历史记录的回填、复制和删除。

## 更多文档

- [开发计划](docs/development-plan.md)
- [系统架构说明](docs/architecture.md)
- [Demo 演示脚本](docs/demo-script.md)
- [交付检查清单](docs/delivery-checklist.md)
- [后端启动与接口说明](docs/backend-guide.md)
- [持久化与可观测性说明](docs/persistence-observability.md)
- [文本处理规则说明](docs/text-processing-guide.md)
- [语音输入前端说明](docs/voice-input-guide.md)
- [历史记录功能说明](docs/history-records-guide.md)
- [热词字典功能说明](docs/hotword-dictionary-guide.md)
