# 后端启动与接口说明

## 后端目前负责什么

当前后端是一个 FastAPI 服务，已经具备这些能力：

- 健康检查：确认后端服务是否启动。
- 文本整理：清理口癖词、规整空白、补基础标点。
- 热词纠错：把常见误识别词替换成项目相关标准词，例如 Python、FastAPI、七牛云。
- 场景格式化：根据通用输入、会议纪要、学习笔记、聊天回复、代码注释等场景生成不同结果。
- 历史记录：把整理后的文本保存到本地 JSON 文件，前端可以读取最近记录。

当前后端还没有直接做“语音识别”。语音转文字目前在浏览器前端通过 Web Speech API 完成，后端负责把识别出来的文字进一步加工。

## 启动方式

必须在项目根目录执行。项目根目录是：

```text
D:\Projects\PyCharmProjects\SmartDictate
```

如果你当前在 `D:\`、`frontend` 或其他目录，直接执行 `uvicorn backend.app.main:app` 会导致 Python 找不到 `backend` 包。

推荐方式一：使用启动脚本。

```bash
scripts\start-backend.cmd
```

推荐方式二：手动进入项目根目录后启动。

```bash
cd /d D:\Projects\PyCharmProjects\SmartDictate
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

如果你使用 Conda 环境 `SmartDictate`，可以这样启动：

```bash
cd /d D:\Projects\PyCharmProjects\SmartDictate
conda activate SmartDictate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

如果你希望开发时自动热重载，并且本机环境允许多进程监听，可以使用：

```bash
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

启动成功后，浏览器访问：

```text
http://127.0.0.1:8000/docs
```

这里会看到 FastAPI 自动生成的接口文档，可以直接测试接口。

## 前后端是否已经联动

已经联动。

前端点击“整理文本”时，会请求：

```http
POST http://127.0.0.1:8000/api/transcripts/process
```

后端返回整理后的文本、字数、清理口癖词数量等指标。前端右侧“最近记录”会请求：

```http
GET http://127.0.0.1:8000/api/transcripts
```

如果前端显示“后端离线”，通常是以下原因：

- 后端没有启动。
- 后端端口不是 8000。
- 前端配置的 `VITE_API_BASE_URL` 和后端地址不一致。
- 浏览器拦截了麦克风或接口请求。

## 配置项

可以复制 `.env.example` 为 `.env`，后续把环境变量放在 `.env` 中。当前代码读取这些配置：

```text
SMART_DICTATE_DATA_FILE=backend/data/transcripts.json
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
VITE_API_BASE_URL=http://127.0.0.1:8000
```

注意：真实 API 密钥不能提交到 Git 仓库，只能放在本地 `.env` 或部署平台的环境变量里。

## 是否应该接网上语音识别 API

可以，而且这是一个很适合本项目的增强方向。

建议分三阶段：

1. MVP 阶段：使用浏览器 Web Speech API，成本最低、响应快、最容易演示。
2. 增强阶段：后端接入在线语音识别 API，提升准确度和稳定性，尤其适合普通话、长音频、专业词汇场景。
3. 扩展阶段：提供本地 faster-whisper 模式，突出隐私、离线和低长期成本。

对于三天实训项目，最推荐的路线是：

```text
Web Speech API 先完成闭环，再把在线 API 做成可选识别通道。
```

这样既能保证作品一定可运行，又能在 README 和路演中讲清楚工程权衡。
