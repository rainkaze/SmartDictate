# 百度语音识别接入说明

本功能把百度语音识别作为 SmartDictate 的可选云端识别通道接入，和浏览器 Web Speech、科大讯飞 IAT / 录音文件转写并列。

## 接入范围

- `baidu_short`：百度短语音识别 REST API，适合 60 秒以内的录音或本机短音频文件。
- `baidu_realtime`：百度实时语音识别 WebSocket API，适合麦克风和标签页音频实时转写。

暂不接入“音频文件转写”异步接口，因为该接口要求音频文件具有公网可访问 URL，和当前项目的本地优先定位不一致。

## 环境变量

```env
BAIDU_ASR_APP_ID=
BAIDU_ASR_API_KEY=
BAIDU_ASR_SECRET_KEY=
BAIDU_ASR_REQUEST_TIMEOUT=45
BAIDU_ASR_REALTIME_IDLE_TIMEOUT=8
```

后端会优先读取 `BAIDU_ASR_*`，同时兼容 `BAIDU_APP_ID`、`BAIDU_API_KEY`、`BAIDU_SECRET_KEY`。

## 模型映射

短语音 REST：

- 中文普通话 / 中英混合：`dev_pid=1537`
- 英语：`dev_pid=1737`
- 方言：`dev_pid=1637`

实时 WebSocket：

- 中文普通话 / 中英混合：`dev_pid=15372`
- 英语：`dev_pid=17372`
- 方言：`dev_pid=15376`

## 前端表现

前端“识别工具”新增“百度 API”。后端返回百度配置可用时，前端会显示：

- “百度短语音识别”：支持麦克风录制、本机文件、标签页音频，模式为短音频听写。
- “百度实时语音识别”：支持麦克风和标签页音频，模式为实时转写。

不支持的音频来源、语言和模式会被动态隐藏或禁用，避免出现未实现的占位功能。
