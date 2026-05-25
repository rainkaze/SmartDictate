import {
  checkHealth,
  clearTranscripts,
  createTranscriptCategory,
  createHotword,
  createAsrStreamUrl,
  deleteHotword,
  deleteTranscript,
  deleteTranscriptAudio,
  listAsrProviders,
  listHotwords,
  listTranscriptCategories,
  listTranscripts,
  processTranscript,
  transcriptAudioUrl,
  transcribeAudio,
  updateTranscript,
  uploadTranscriptAudio,
} from "./modules/api-client.js";
import { createPcmStreamRecorder, createWavRecorder } from "./modules/audio-recorder.js";
import { escapeHtml } from "./modules/html.js";
import { createSpeechRecognitionController } from "./modules/speech-recognition.js";
import "./styles.css";

const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  navButtons: Array.from(document.querySelectorAll("[data-view-target]")),
  views: Array.from(document.querySelectorAll("[data-view]")),
  sceneSelect: document.querySelector("#sceneSelect"),
  vendorSelect: document.querySelector("#vendorSelect"),
  apiField: document.querySelector("#apiField"),
  providerSelect: document.querySelector("#providerSelect"),
  sourceSelect: document.querySelector("#sourceSelect"),
  languageSelect: document.querySelector("#languageSelect"),
  modeSelect: document.querySelector("#modeSelect"),
  fileField: document.querySelector("#fileField"),
  audioFileInput: document.querySelector("#audioFileInput"),
  saveAudioCheckbox: document.querySelector("#saveAudioCheckbox"),
  saveAudioHint: document.querySelector("#saveAudioHint"),
  recordButton: document.querySelector("#recordButton"),
  sampleButton: document.querySelector("#sampleButton"),
  processButton: document.querySelector("#processButton"),
  copyButton: document.querySelector("#copyButton"),
  clearButton: document.querySelector("#clearButton"),
  refreshHistoryButton: document.querySelector("#refreshHistoryButton"),
  clearHistoryButton: document.querySelector("#clearHistoryButton"),
  historySearchInput: document.querySelector("#historySearchInput"),
  historyCategoryFilter: document.querySelector("#historyCategoryFilter"),
  historyFavoriteFilter: document.querySelector("#historyFavoriteFilter"),
  categoryForm: document.querySelector("#categoryForm"),
  categoryNameInput: document.querySelector("#categoryNameInput"),
  categoryColorInput: document.querySelector("#categoryColorInput"),
  hotwordForm: document.querySelector("#hotwordForm"),
  hotwordSource: document.querySelector("#hotwordSource"),
  hotwordTarget: document.querySelector("#hotwordTarget"),
  hotwordStatus: document.querySelector("#hotwordStatus"),
  hotwordList: document.querySelector("#hotwordList"),
  recognitionPanel: document.querySelector("#recognitionPanel"),
  recognitionStatus: document.querySelector("#recognitionStatus"),
  interimText: document.querySelector("#interimText"),
  streamPhase: document.querySelector("#streamPhase"),
  streamSource: document.querySelector("#streamSource"),
  streamTransport: document.querySelector("#streamTransport"),
  waveformBars: Array.from(document.querySelectorAll("#waveform span")),
  copyStatus: document.querySelector("#copyStatus"),
  rawText: document.querySelector("#rawText"),
  processedText: document.querySelector("#processedText"),
  rawLength: document.querySelector("#rawLength"),
  processedLength: document.querySelector("#processedLength"),
  removedFillers: document.querySelector("#removedFillers"),
  elapsedSeconds: document.querySelector("#elapsedSeconds"),
  historyList: document.querySelector("#historyList"),
  sessionDetailPanel: document.querySelector("#sessionDetailPanel"),
  sessionDetailHeading: document.querySelector("#sessionDetailHeading"),
  sessionDetailStatus: document.querySelector("#sessionDetailStatus"),
  sessionDetailEmpty: document.querySelector("#sessionDetailEmpty"),
  sessionDetailForm: document.querySelector("#sessionDetailForm"),
  sessionTitleInput: document.querySelector("#sessionTitleInput"),
  sessionCategorySelect: document.querySelector("#sessionCategorySelect"),
  sessionSceneSelect: document.querySelector("#sessionSceneSelect"),
  sessionFavoriteCheckbox: document.querySelector("#sessionFavoriteCheckbox"),
  sessionRawText: document.querySelector("#sessionRawText"),
  sessionProcessedText: document.querySelector("#sessionProcessedText"),
  sessionAudioMeta: document.querySelector("#sessionAudioMeta"),
  sessionAudioPlayer: document.querySelector("#sessionAudioPlayer"),
  sessionAudioInput: document.querySelector("#sessionAudioInput"),
  replaceSessionAudioButton: document.querySelector("#replaceSessionAudioButton"),
  deleteSessionAudioButton: document.querySelector("#deleteSessionAudioButton"),
  saveSessionButton: document.querySelector("#saveSessionButton"),
  copySessionButton: document.querySelector("#copySessionButton"),
  sendSessionToWorkbenchButton: document.querySelector("#sendSessionToWorkbenchButton"),
  deleteSessionButton: document.querySelector("#deleteSessionButton"),
};

const sampleText =
  "嗯我想用 SmartDictate 整理二叉树的遍历笔记，二叉树的遍历包括前序遍历、中序遍历、后序遍历以及层序遍历。";

const state = {
  startedAt: null,
  timerId: null,
  historyItems: [],
  historyCategories: [],
  historyFilters: {
    categoryId: "",
    favoriteOnly: false,
    query: "",
  },
  historySearchTimer: null,
  selectedSessionId: null,
  pendingAudioAttachment: null,
  hotwordItems: [],
  asrProviders: [],
  streamSocket: null,
  recognitionPhase: "idle",
  streamLevel: 0,
};

const providerFallbacks = {
  browser: {
    id: "browser",
    label: "浏览器 Web Speech API",
    enabled: true,
    supported_sources: ["microphone"],
    supported_languages: ["zh_cn", "zh_en", "en_us"],
    supported_modes: ["realtime"],
  },
  xfyun_iat: {
    id: "xfyun_iat",
    label: "语音听写 IAT",
    enabled: false,
    supported_sources: ["microphone", "system"],
    supported_languages: ["zh_cn", "zh_en", "en_us", "ja_jp", "dialect"],
    supported_modes: ["realtime"],
  },
  xfyun_lfasr_large: {
    id: "xfyun_lfasr_large",
    label: "录音文件转写大模型",
    enabled: false,
    supported_sources: ["microphone", "file", "system"],
    supported_languages: ["zh_cn", "zh_en"],
    supported_modes: ["long"],
  },
  future: {
    id: "future",
    label: "待扩展接口",
    enabled: false,
    supported_sources: [],
    supported_languages: [],
    supported_modes: [],
  },
};

const vendorProviders = {
  browser: ["browser"],
  xfyun: ["xfyun_iat", "xfyun_lfasr_large"],
};

const sourceLabels = {
  microphone: "直接监听麦克风",
  file: "选择本机音频文件",
  system: "扬声器 / 标签页音频",
};

const languageLabels = {
  zh_en: "中英混合",
  zh_cn: "中文普通话",
  en_us: "英语",
  ja_jp: "日语",
  dialect: "方言",
};

const modeLabels = {
  short: "短音频听写",
  realtime: "实时转写",
  long: "录音文件转写",
};

const sourceCompactLabels = {
  idle: "未采集",
  microphone: "麦克风",
  file: "本机文件",
  system: "标签页音频",
};

const phaseLabels = {
  idle: "待输入",
  connecting: "连接中",
  capturing: "采集中",
  recognizing: "识别中",
  closing: "收尾中",
  done: "已完成",
  error: "异常",
};

const UNCATEGORIZED_CATEGORY_ID = "uncategorized";

const wavRecorder = createWavRecorder();
const pcmStreamRecorder = createPcmStreamRecorder();

function setActiveView(viewName) {
  for (const view of elements.views) {
    view.classList.toggle("active", view.dataset.view === viewName);
  }
  for (const button of elements.navButtons) {
    button.classList.toggle("active", button.dataset.viewTarget === viewName);
  }
}

const speechController = createSpeechRecognitionController({
  onStart: () => {
    state.startedAt = Date.now();
    startElapsedTimer();
    elements.recordButton.textContent = "停止识别";
    elements.recordButton.classList.add("recording");
    setRecognitionPhase("capturing", {
      status: "浏览器正在监听",
      source: "microphone",
      transport: "Web Speech",
      detail: "请开始说话。",
    });
  },
  onStop: () => {
    stopElapsedTimer();
    elements.recordButton.textContent = "开始识别";
    elements.recordButton.classList.remove("recording");
    setRecognitionPhase("done", {
      status: "已停止",
      source: "microphone",
      transport: "Web Speech",
      detail: "浏览器识别已停止。",
      level: 0,
    });
  },
  onFinalText: (text) => {
    appendRawText(text);
    updateMetrics();
  },
  onInterimText: (text) => {
    setRecognitionPhase("recognizing", {
      status: "浏览器识别中",
      source: "microphone",
      transport: "Web Speech",
      detail: text || "正在等待更清晰的语音输入。",
    });
  },
  onError: (message) => {
    stopElapsedTimer();
    setRecognitionPhase("error", {
      status: message,
      source: "microphone",
      transport: "Web Speech",
      level: 0,
    });
    elements.recordButton.textContent = "开始识别";
    elements.recordButton.classList.remove("recording");
  },
});

function setApiStatus(online) {
  elements.apiStatus.textContent = online ? "后端在线" : "后端离线";
  elements.apiStatus.classList.toggle("offline", !online);
}

function setRecognitionPhase(phase, options = {}) {
  state.recognitionPhase = phase;
  elements.recognitionPanel.dataset.streamState = phase;
  elements.streamPhase.textContent = phaseLabels[phase] ?? phase;

  if (options.status) {
    elements.recognitionStatus.textContent = options.status;
  }
  if (options.source) {
    elements.streamSource.textContent = sourceCompactLabels[options.source] ?? options.source;
  }
  if (options.transport) {
    elements.streamTransport.textContent = options.transport;
  }
  if (options.detail) {
    elements.interimText.textContent = options.detail;
  }
  if (typeof options.level === "number") {
    updateWaveform(options.level);
  }
}

function resetRecognitionPhase(detail = null) {
  setRecognitionPhase("idle", {
    status: "等待输入",
    source: "idle",
    transport: "本地待命",
    detail: detail ?? "选择识别方式后开始输入。",
    level: 0,
  });
}

function setRecognitionHint(message) {
  if (state.recognitionPhase === "idle") {
    elements.interimText.textContent = message;
  }
}

function updateWaveform(level) {
  const normalized = Math.max(0, Math.min(1, level));
  state.streamLevel = normalized === 0 ? 0 : state.streamLevel * 0.62 + normalized * 0.38;

  elements.waveformBars.forEach((bar, index) => {
    const curve = 0.58 + Math.sin(index * 1.4) * 0.22 + (index % 5) * 0.035;
    const height = Math.max(0.12, Math.min(1, 0.14 + state.streamLevel * curve));
    bar.style.transform = `scaleY(${height})`;
    bar.style.opacity = String(Math.max(0.35, Math.min(1, 0.42 + state.streamLevel * 0.72)));
  });
}

async function refreshApiStatus() {
  setApiStatus(await checkHealth());
}

async function loadAsrProviders() {
  try {
    state.asrProviders = await listAsrProviders();
    setApiStatus(true);
  } catch {
    state.asrProviders = [];
    setApiStatus(false);
  }
  syncVendorOptions();
  syncRecognitionControls();
}

function getProviderInfo(providerId = elements.providerSelect.value) {
  return (
    state.asrProviders.find((item) => item.id === providerId) ??
    providerFallbacks[providerId] ??
    providerFallbacks.future
  );
}

function syncVendorOptions() {
  const xfyunReady = vendorProviders.xfyun.some((providerId) => getProviderInfo(providerId).enabled);

  for (const option of elements.vendorSelect.options) {
    if (option.value === "browser") {
      option.disabled = false;
      option.textContent = "本机浏览器识别";
    } else if (option.value === "xfyun") {
      option.disabled = !xfyunReady;
      option.textContent = xfyunReady ? "科大讯飞 API" : "科大讯飞 API（未配置）";
    } else {
      option.disabled = true;
    }
  }

  if (elements.vendorSelect.selectedOptions[0]?.disabled) {
    elements.vendorSelect.value = "browser";
  }
}

function syncProviderOptions() {
  const providerIds = vendorProviders[elements.vendorSelect.value] ?? [];
  elements.apiField.classList.toggle("hidden", providerIds.length <= 1);

  for (const option of elements.providerSelect.options) {
    const visible = providerIds.includes(option.value);
    const provider = getProviderInfo(option.value);
    option.hidden = !visible;
    option.disabled = !visible || !provider.enabled;
    option.textContent = provider.enabled ? provider.label : `${provider.label}（未配置）`;
  }

  const selected = elements.providerSelect.selectedOptions[0];
  if (!selected || selected.hidden || selected.disabled) {
    const firstEnabled = providerIds.find((providerId) => getProviderInfo(providerId).enabled);
    elements.providerSelect.value = firstEnabled ?? providerIds[0] ?? "browser";
  }
}

function appendRawText(text) {
  const current = elements.rawText.value.trim();
  elements.rawText.value = current ? `${current} ${text}` : text;
}

function replaceRawText(text) {
  elements.rawText.value = text;
  elements.processedText.value = "";
  elements.copyStatus.textContent = "未复制";
  elements.removedFillers.textContent = "0";
}

function startElapsedTimer() {
  stopElapsedTimer();
  state.timerId = window.setInterval(updateElapsedSeconds, 500);
  updateElapsedSeconds();
}

function stopElapsedTimer() {
  if (state.timerId) {
    window.clearInterval(state.timerId);
    state.timerId = null;
  }
  updateElapsedSeconds();
}

function updateElapsedSeconds() {
  if (!state.startedAt) {
    elements.elapsedSeconds.textContent = "0s";
    return;
  }

  const seconds = Math.max(0, Math.round((Date.now() - state.startedAt) / 1000));
  elements.elapsedSeconds.textContent = `${seconds}s`;
}

async function handleRecognition() {
  syncRecognitionControls();
  const provider = elements.providerSelect.value;
  const source = elements.sourceSelect.value;

  if (provider === "browser") {
    clearPendingAudioAttachment();
    speechController.toggle(elements.languageSelect.value);
    return;
  }
  if (provider === "xfyun_iat") {
    if (pcmStreamRecorder.isRecording()) {
      await stopIatStreamRecognition();
    } else {
      await startIatStreamRecognition(source);
    }
    return;
  }

  if (source === "file") {
    await transcribeSelectedFile();
    return;
  }

  if (wavRecorder.isRecording()) {
    await stopApiRecordingAndTranscribe();
    return;
  }

  await startApiRecording(source);
}

async function startIatStreamRecognition(source) {
  clearPendingAudioAttachment();
  const url = createAsrStreamUrl({
    provider: elements.providerSelect.value,
    source,
    language: elements.languageSelect.value,
  });

  elements.recordButton.disabled = true;
  setRecognitionPhase("connecting", {
    status: "正在连接 IAT",
    source,
    transport: "WebSocket 连接中",
    detail: "正在建立实时识别通道。",
    level: 0,
  });

  const socket = await openStreamSocket(url);
  state.streamSocket = socket;
  bindStreamSocket(socket);

  try {
    state.startedAt = Date.now();
    startElapsedTimer();
    await pcmStreamRecorder.start(source, {
      onChunk: (chunk) => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(chunk);
        }
      },
      onLevel: updateWaveform,
      captureAudio: shouldSaveAudio(),
    });
    elements.processedText.value = "";
    elements.copyStatus.textContent = "未复制";
    elements.removedFillers.textContent = "0";
    elements.recordButton.textContent = "停止实时识别";
    elements.recordButton.classList.add("recording");
    setRecognitionPhase("capturing", {
      status: source === "system" ? "正在转写标签页音频" : "正在转写麦克风",
      source,
      transport: "16k PCM 流",
      detail: "音频已开始实时送入 IAT。",
    });
  } catch (error) {
    socket.close();
    state.streamSocket = null;
    stopElapsedTimer();
    elements.recordButton.classList.remove("recording");
    setRecognitionPhase("error", {
      status: error.message,
      source,
      transport: "连接中断",
      level: 0,
    });
  } finally {
    elements.recordButton.disabled = false;
  }
}

async function stopIatStreamRecognition() {
  elements.recordButton.disabled = true;
  setRecognitionPhase("closing", {
    status: "正在收尾识别",
    source: elements.sourceSelect.value,
    transport: "等待最终结果",
    detail: "已停止采集，正在等待 IAT 返回最终文本。",
    level: 0,
  });

  const recording = await pcmStreamRecorder.stop();
  if (recording?.blob) {
    setPendingAudioAttachment(recording.blob, recording.filename, recording.durationMs);
  }
  if (state.streamSocket?.readyState === WebSocket.OPEN) {
    state.streamSocket.send("stop");
  }

  elements.recordButton.classList.remove("recording");
  elements.recordButton.textContent = "开始实时识别";
  elements.recordButton.disabled = false;
}

function openStreamSocket(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url);
    socket.binaryType = "arraybuffer";
    socket.addEventListener("open", () => resolve(socket), { once: true });
    socket.addEventListener(
      "error",
      () => reject(new Error("IAT 实时识别连接失败，请确认后端服务和讯飞配置。")),
      { once: true },
    );
  });
}

function bindStreamSocket(socket) {
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    const source = elements.sourceSelect.value;
    if (payload.type === "ready") {
      setRecognitionPhase("capturing", {
        status: "实时通道已就绪",
        source,
        transport: "WebSocket 已连接",
        detail: payload.message,
      });
      return;
    }
    if (payload.type === "partial") {
      elements.rawText.value = payload.text;
      setRecognitionPhase("recognizing", {
        status: "实时识别中",
        source,
        transport: "IAT 返回片段",
        detail: payload.segment || "正在接收识别片段",
      });
      updateMetrics();
      return;
    }
    if (payload.type === "final") {
      elements.rawText.value = payload.text;
      setRecognitionPhase("done", {
        status: payload.text ? "实时识别完成" : "未识别到文本",
        source,
        transport: "最终结果",
        detail: `IAT 实时识别完成，耗时 ${payload.duration_ms}ms`,
        level: 0,
      });
      updateMetrics();
      return;
    }
    if (payload.type === "error") {
      setRecognitionPhase("error", {
        status: payload.message,
        source,
        transport: "识别中断",
        detail: "实时识别已中断，请检查 API 凭据、网络或音频权限。",
        level: 0,
      });
      socket.close();
    }
  });

  socket.addEventListener("close", async () => {
    const settled = ["done", "error"].includes(state.recognitionPhase);
    state.streamSocket = null;
    if (pcmStreamRecorder.isRecording()) {
      const recording = await pcmStreamRecorder.stop();
      if (recording?.blob) {
        setPendingAudioAttachment(recording.blob, recording.filename, recording.durationMs);
      }
    }
    stopElapsedTimer();
    elements.recordButton.classList.remove("recording");
    if (!settled) {
      setRecognitionPhase("error", {
        status: "实时连接已关闭",
        source: elements.sourceSelect.value,
        transport: "WebSocket 关闭",
        detail: "实时通道提前关闭，未收到最终识别结果。",
        level: 0,
      });
    }
    syncRecognitionControls();
  });
}

async function startApiRecording(source) {
  try {
    state.startedAt = Date.now();
    startElapsedTimer();
    await wavRecorder.start(source);
    elements.recordButton.textContent = "停止并识别";
    elements.recordButton.classList.add("recording");
    setRecognitionPhase("capturing", {
      status: source === "system" ? "正在采集扬声器音频" : "正在录制麦克风",
      source,
      transport: "本地录音",
      detail:
        source === "system"
          ? "请选择要共享音频的标签页或窗口，停止后会上传识别。"
          : "录制完成后会上传到所选识别 API。",
    });
  } catch (error) {
    stopElapsedTimer();
    elements.recordButton.classList.remove("recording");
    elements.recordButton.textContent = "开始识别";
    setRecognitionPhase("error", {
      status: error.message,
      source,
      transport: "采集失败",
      level: 0,
    });
  }
}

async function stopApiRecordingAndTranscribe() {
  elements.recordButton.disabled = true;
  setRecognitionPhase("closing", {
    status: "正在上传识别",
    source: elements.sourceSelect.value,
    transport: "上传音频",
    detail: "已停止采集，正在上传到所选识别接口。",
    level: 0,
  });

  try {
    const recording = await wavRecorder.stop();
    elements.recordButton.classList.remove("recording");
    elements.recordButton.textContent = "开始识别";
    if (!recording || recording.blob.size === 0) {
      setRecognitionPhase("error", {
        status: "没有采集到音频",
        source: elements.sourceSelect.value,
        transport: "采集为空",
        level: 0,
      });
      return;
    }
    if (shouldSaveAudio()) {
      setPendingAudioAttachment(recording.blob, recording.filename, recording.durationMs);
    } else {
      clearPendingAudioAttachment();
    }
    await uploadAndReplace(recording.blob, recording.filename);
  } finally {
    stopElapsedTimer();
    elements.recordButton.disabled = false;
    syncRecognitionControls();
  }
}

async function transcribeSelectedFile() {
  const file = elements.audioFileInput.files?.[0];
  if (!file) {
    setRecognitionPhase("error", {
      status: "请先选择本机音频文件",
      source: "file",
      transport: "缺少文件",
      detail: "当前接口需要先选择一个本机音频文件。",
      level: 0,
    });
    return;
  }

  state.startedAt = Date.now();
  startElapsedTimer();
  elements.recordButton.disabled = true;
  setRecognitionPhase("closing", {
    status: "正在上传音频文件",
    source: "file",
    transport: "上传音频",
    detail: "正在读取本机文件并提交到识别接口。",
    level: 0,
  });

  try {
    if (shouldSaveAudio()) {
      setPendingAudioAttachment(file, file.name, null);
    } else {
      clearPendingAudioAttachment();
    }
    await uploadAndReplace(file, file.name);
  } finally {
    stopElapsedTimer();
    elements.recordButton.disabled = false;
    syncRecognitionControls();
  }
}

async function uploadAndReplace(audioBlob, filename) {
  try {
    const result = await transcribeAudio({
      audioBlob,
      filename,
      provider: elements.providerSelect.value,
      source: elements.sourceSelect.value,
      language: elements.languageSelect.value,
      mode: elements.modeSelect.value,
    });

    replaceRawText(result.raw_text);
    updateMetrics();
    setApiStatus(true);
    setRecognitionPhase("done", {
      status: result.raw_text ? "识别完成" : "识别完成但未返回文本",
      source: elements.sourceSelect.value,
      transport: providerLabel(result.provider),
      detail: `识别接口：${providerLabel(result.provider)}，耗时 ${result.duration_ms}ms`,
      level: 0,
    });
  } catch (error) {
    setApiStatus(error instanceof TypeError ? false : true);
    setRecognitionPhase("error", {
      status: error.message,
      source: elements.sourceSelect.value,
      transport: "识别失败",
      detail: "后端已返回识别错误，请按提示检查 API 凭据、服务权限或音频格式。",
      level: 0,
    });
  }
}

function shouldSaveAudio() {
  return Boolean(elements.saveAudioCheckbox.checked);
}

function setPendingAudioAttachment(blob, filename, durationMs) {
  state.pendingAudioAttachment = {
    blob,
    filename: filename || `smartdictate-${Date.now()}.wav`,
    durationMs,
  };
}

function clearPendingAudioAttachment() {
  state.pendingAudioAttachment = null;
}

async function handleProcessText() {
  const rawText = elements.rawText.value.trim();
  if (!rawText) {
    elements.recognitionStatus.textContent = "请先输入文本";
    return;
  }

  elements.processButton.disabled = true;
  elements.processButton.textContent = "整理中";

  try {
    const item = await processTranscript({
      rawText,
      scene: elements.sceneSelect.value,
    });
    if (state.pendingAudioAttachment) {
      await uploadTranscriptAudio(item.id, {
        audioBlob: state.pendingAudioAttachment.blob,
        filename: state.pendingAudioAttachment.filename,
        durationMs: state.pendingAudioAttachment.durationMs,
      });
      clearPendingAudioAttachment();
    }
    elements.processedText.value = item.processed_text;
    renderMetrics(item.metrics);
    await loadHistory();
    setApiStatus(true);
  } catch {
    elements.recognitionStatus.textContent = "后端不可用，请先启动 FastAPI 服务";
    setApiStatus(false);
  } finally {
    elements.processButton.disabled = false;
    elements.processButton.textContent = "整理文本";
  }
}

async function handleCopyResult() {
  await copyText(elements.processedText.value.trim(), elements.copyStatus);
}

function handleClearText() {
  elements.rawText.value = "";
  elements.processedText.value = "";
  elements.copyStatus.textContent = "未复制";
  elements.removedFillers.textContent = "0";
  state.startedAt = null;
  clearPendingAudioAttachment();
  stopElapsedTimer();
  resetRecognitionPhase("已清空当前文本。");
  updateMetrics();
}

function handleFillSample() {
  clearPendingAudioAttachment();
  replaceRawText(sampleText);
  setRecognitionPhase("done", {
    status: "已填入示例",
    source: "idle",
    transport: "手动输入",
    detail: "可以直接点击“整理文本”验证前后端联动。",
    level: 0,
  });
  updateMetrics();
}

function updateMetrics() {
  elements.rawLength.textContent = String(elements.rawText.value.length);
  elements.processedLength.textContent = String(elements.processedText.value.length);
}

function renderMetrics(metrics) {
  elements.rawLength.textContent = String(metrics.raw_length);
  elements.processedLength.textContent = String(metrics.processed_length);
  elements.removedFillers.textContent = String(metrics.removed_fillers);
}

async function loadHistory() {
  try {
    state.historyItems = await listTranscripts({
      limit: 20,
      categoryId: state.historyFilters.categoryId,
      favorite: state.historyFilters.favoriteOnly ? true : null,
      query: state.historyFilters.query,
    });
    renderHistory(state.historyItems);
    setApiStatus(true);
  } catch {
    elements.historyList.innerHTML = '<p class="history-empty">启动后端后可查看会话库。</p>';
    setApiStatus(false);
  }
}

async function loadCategories() {
  try {
    state.historyCategories = await listTranscriptCategories();
    renderCategoryFilters();
    setApiStatus(true);
  } catch {
    state.historyCategories = [];
    renderCategoryFilters();
    setApiStatus(false);
  }
}

async function loadSessionLibrary() {
  await loadCategories();
  await loadHistory();
}

function renderCategoryFilters() {
  const currentValue = elements.historyCategoryFilter.value;
  const options = [
    '<option value="">全部分类</option>',
    `<option value="${UNCATEGORIZED_CATEGORY_ID}">未分类</option>`,
    ...state.historyCategories.map(
      (category) => `<option value="${escapeHtml(category.id)}">${escapeHtml(category.name)}</option>`,
    ),
  ];
  elements.historyCategoryFilter.innerHTML = options.join("");
  const hasCurrentValue = Array.from(elements.historyCategoryFilter.options).some(
    (option) => option.value === currentValue,
  );
  elements.historyCategoryFilter.value = hasCurrentValue ? currentValue : "";
  state.historyFilters.categoryId = elements.historyCategoryFilter.value;
  const selectedSession = getSelectedSession();
  if (selectedSession && !elements.sessionDetailForm.classList.contains("hidden")) {
    renderSessionCategoryOptions(selectedSession.category_id);
  }
}

function renderHistory(items) {
  if (!items.length) {
    elements.historyList.innerHTML = state.historyFilters.query
      ? '<p class="history-empty">没有匹配的会话。</p>'
      : '<p class="history-empty">暂无会话记录。</p>';
    return;
  }

  elements.historyList.innerHTML = items.map(renderHistoryItem).join("");

  for (const button of elements.historyList.querySelectorAll("button[data-action]")) {
    button.addEventListener("click", () => {
      handleHistoryAction(button.dataset.action, button.dataset.historyId);
    });
  }
  for (const select of elements.historyList.querySelectorAll("select[data-action='category']")) {
    select.addEventListener("change", () => {
      handleHistoryCategoryChange(select.dataset.historyId, select.value);
    });
  }
}

function renderHistoryItem(item) {
  const time = new Date(item.updated_at ?? item.created_at).toLocaleString();
  const category = getCategory(item.category_id);
  const categoryName = category?.name ?? "未分类";
  const categoryColor = category?.color ?? "#94a3b8";
  const favoriteClass = item.favorite ? " is-favorite" : "";
  const favoriteLabel = item.favorite ? "取消收藏" : "收藏";
  return `
    <article class="history-item${favoriteClass}">
      <div class="history-title-row">
        <button
          class="favorite-button"
          type="button"
          aria-pressed="${item.favorite ? "true" : "false"}"
          title="${favoriteLabel}"
          data-action="favorite"
          data-history-id="${item.id}"
        >${item.favorite ? "★" : "☆"}</button>
        <div>
          <strong>${escapeHtml(item.title ?? "未命名会话")}</strong>
          <div class="history-meta">
            <span class="category-chip" style="--category-color: ${categoryColor}">${escapeHtml(categoryName)}</span>
            <span>${sceneLabel(item.scene)}</span>
            <span>${time}</span>
            <span>${item.metrics.processed_length} 字</span>
          </div>
        </div>
      </div>
      <p class="history-text">${escapeHtml(item.processed_text)}</p>
      <div class="history-edit-row">
        <select data-action="category" data-history-id="${item.id}" aria-label="会话分类">
          ${renderHistoryCategoryOptions(item.category_id)}
        </select>
        <button class="text-button" type="button" data-action="rename" data-history-id="${item.id}">重命名</button>
      </div>
      <div class="history-meta">
        <span>原文 ${item.metrics.raw_length} 字</span>
        <span>清理 ${item.metrics.removed_fillers} 处</span>
        <span>${item.audio ? "有音频" : "无音频"}</span>
      </div>
      <div class="history-actions">
        <button class="secondary-button" type="button" data-action="open" data-history-id="${item.id}">打开</button>
        <button class="secondary-button" type="button" data-action="copy" data-history-id="${item.id}">复制</button>
        <button class="text-button danger-text" type="button" data-action="delete" data-history-id="${item.id}">删除</button>
      </div>
    </article>
  `;
}

function renderHistoryCategoryOptions(selectedCategoryId) {
  const selected = selectedCategoryId ?? "";
  const options = [
    `<option value="" ${selected === "" ? "selected" : ""}>未分类</option>`,
    ...state.historyCategories.map((category) => {
      const isSelected = selected === category.id ? "selected" : "";
      return `<option value="${escapeHtml(category.id)}" ${isSelected}>${escapeHtml(category.name)}</option>`;
    }),
  ];
  return options.join("");
}

function getCategory(categoryId) {
  if (!categoryId) {
    return null;
  }
  return state.historyCategories.find((category) => category.id === categoryId) ?? null;
}

function openSessionDetail(item) {
  state.selectedSessionId = item.id;
  elements.sessionDetailEmpty.classList.add("hidden");
  elements.sessionDetailForm.classList.remove("hidden");
  elements.sessionDetailHeading.textContent = item.title ?? "会话详情";
  elements.sessionDetailStatus.textContent = item.favorite ? "已收藏" : "可编辑";
  elements.sessionTitleInput.value = item.title ?? "";
  elements.sessionSceneSelect.value = item.scene;
  elements.sessionFavoriteCheckbox.checked = Boolean(item.favorite);
  elements.sessionRawText.value = item.raw_text;
  elements.sessionProcessedText.value = item.processed_text;
  renderSessionCategoryOptions(item.category_id);
  renderSessionAudio(item);
}

function renderSessionCategoryOptions(selectedCategoryId) {
  elements.sessionCategorySelect.innerHTML = renderHistoryCategoryOptions(selectedCategoryId);
}

function renderSessionAudio(item) {
  if (!item.audio) {
    elements.sessionAudioMeta.textContent = "未保存音频";
    elements.sessionAudioPlayer.removeAttribute("src");
    elements.sessionAudioPlayer.classList.add("hidden");
    elements.deleteSessionAudioButton.disabled = true;
    return;
  }

  const size = formatFileSize(item.audio.size_bytes);
  const duration =
    typeof item.audio.duration_ms === "number" ? ` · ${formatDuration(item.audio.duration_ms)}` : "";
  elements.sessionAudioMeta.textContent = `${item.audio.filename} · ${size}${duration}`;
  elements.sessionAudioPlayer.src = transcriptAudioUrl(item.id);
  elements.sessionAudioPlayer.classList.remove("hidden");
  elements.deleteSessionAudioButton.disabled = false;
}

function getSelectedSession() {
  return state.historyItems.find((item) => item.id === state.selectedSessionId) ?? null;
}

async function handleSaveSession(event) {
  event.preventDefault();
  if (!state.selectedSessionId) {
    return;
  }

  const updated = await updateTranscript(state.selectedSessionId, {
    title: elements.sessionTitleInput.value.trim(),
    raw_text: elements.sessionRawText.value,
    processed_text: elements.sessionProcessedText.value,
    scene: elements.sessionSceneSelect.value,
    category_id: elements.sessionCategorySelect.value || null,
    favorite: elements.sessionFavoriteCheckbox.checked,
  });
  await loadHistory();
  openSessionDetail(updated);
  elements.sessionDetailStatus.textContent = "已保存";
}

async function handleReplaceSessionAudio() {
  const file = elements.sessionAudioInput.files?.[0];
  if (!state.selectedSessionId || !file) {
    return;
  }

  const updated = await uploadTranscriptAudio(state.selectedSessionId, {
    audioBlob: file,
    filename: file.name,
    durationMs: null,
  });
  elements.sessionAudioInput.value = "";
  await loadHistory();
  openSessionDetail(updated);
}

async function handleDeleteSessionAudio() {
  if (!state.selectedSessionId) {
    return;
  }
  await deleteTranscriptAudio(state.selectedSessionId);
  await loadHistory();
  const item = state.historyItems.find((entry) => entry.id === state.selectedSessionId);
  if (item) {
    openSessionDetail(item);
  }
}

async function handleDeleteSelectedSession() {
  if (!state.selectedSessionId) {
    return;
  }
  const confirmed = window.confirm("确定要删除当前会话吗？此操作不可撤销。");
  if (!confirmed) {
    return;
  }
  await deleteTranscript(state.selectedSessionId);
  state.selectedSessionId = null;
  elements.sessionDetailForm.classList.add("hidden");
  elements.sessionDetailEmpty.classList.remove("hidden");
  elements.sessionDetailStatus.textContent = "已删除";
  await loadHistory();
}

function handleSendSessionToWorkbench() {
  const item = getSelectedSession();
  if (!item) {
    return;
  }
  elements.rawText.value = elements.sessionRawText.value;
  elements.processedText.value = elements.sessionProcessedText.value;
  elements.sceneSelect.value = elements.sessionSceneSelect.value;
  renderMetrics({
    raw_length: elements.sessionRawText.value.length,
    processed_length: elements.sessionProcessedText.value.length,
    removed_fillers: item.metrics.removed_fillers,
  });
  setRecognitionPhase("done", {
    status: "已发送到工作台",
    source: "idle",
    transport: "会话库",
    detail: elements.sessionTitleInput.value,
    level: 0,
  });
  setActiveView("workbench");
}

async function handleHistoryAction(action, id) {
  const item = state.historyItems.find((entry) => entry.id === id);
  if (!item) {
    return;
  }

  if (action === "open") {
    openSessionDetail(item);
    setActiveView("sessions");
    return;
  }

  if (action === "copy") {
    await copyText(item.processed_text);
    return;
  }

  if (action === "favorite") {
    await updateTranscript(id, { favorite: !item.favorite });
    await loadHistory();
    return;
  }

  if (action === "rename") {
    const title = window.prompt("请输入会话标题", item.title ?? "");
    if (title === null) {
      return;
    }
    const normalizedTitle = title.trim();
    if (!normalizedTitle) {
      window.alert("会话标题不能为空。");
      return;
    }
    await updateTranscript(id, { title: normalizedTitle });
    await loadHistory();
    return;
  }

  if (action === "delete") {
    await deleteTranscript(id);
    if (state.selectedSessionId === id) {
      state.selectedSessionId = null;
      elements.sessionDetailForm.classList.add("hidden");
      elements.sessionDetailEmpty.classList.remove("hidden");
      elements.sessionDetailStatus.textContent = "已删除";
    }
    await loadHistory();
  }
}

async function handleHistoryCategoryChange(id, categoryId) {
  await updateTranscript(id, { category_id: categoryId || null });
  await loadHistory();
}

async function handleClearHistory() {
  if (!state.historyItems.length) {
    return;
  }

  const confirmed = window.confirm("确定要清空全部历史记录吗？此操作不可撤销。");
  if (!confirmed) {
    return;
  }

  await clearTranscripts();
  state.selectedSessionId = null;
  elements.sessionDetailForm.classList.add("hidden");
  elements.sessionDetailEmpty.classList.remove("hidden");
  elements.sessionDetailStatus.textContent = "已清空";
  await loadHistory();
}

async function handleAddCategory(event) {
  event.preventDefault();
  const name = elements.categoryNameInput.value.trim();
  if (!name) {
    return;
  }

  try {
    await createTranscriptCategory({
      name,
      color: elements.categoryColorInput.value,
    });
    elements.categoryNameInput.value = "";
    await loadSessionLibrary();
  } catch (error) {
    window.alert(error.message);
  }
}

function handleHistoryFilterChange() {
  state.historyFilters.categoryId = elements.historyCategoryFilter.value;
  state.historyFilters.favoriteOnly = elements.historyFavoriteFilter.checked;
  loadHistory();
}

function handleHistorySearchInput() {
  window.clearTimeout(state.historySearchTimer);
  state.historySearchTimer = window.setTimeout(() => {
    state.historyFilters.query = elements.historySearchInput.value.trim();
    loadHistory();
  }, 180);
}

async function loadHotwords() {
  try {
    state.hotwordItems = await listHotwords();
    renderHotwords(state.hotwordItems);
    elements.hotwordStatus.textContent = `${state.hotwordItems.length} 条`;
    setApiStatus(true);
  } catch {
    elements.hotwordStatus.textContent = "加载失败";
    elements.hotwordList.innerHTML = '<p class="history-time">启动后端后可维护热词。</p>';
    setApiStatus(false);
  }
}

function renderHotwords(items) {
  if (!items.length) {
    elements.hotwordList.innerHTML = '<p class="history-time">暂无热词。</p>';
    return;
  }

  elements.hotwordList.innerHTML = items
    .map((item) => {
      const badge = item.builtin ? "内置" : "自定义";
      const action = item.builtin
        ? '<span class="history-time">不可删除</span>'
        : `<button class="text-button danger-text" type="button" data-hotword-source="${escapeHtml(item.source)}">删除</button>`;
      return `
        <article class="hotword-item">
          <div>
            <strong>${escapeHtml(item.source)}</strong>
            <span>-></span>
            <strong>${escapeHtml(item.target)}</strong>
          </div>
          <div class="hotword-meta">
            <span>${badge}</span>
            ${action}
          </div>
        </article>
      `;
    })
    .join("");

  for (const button of elements.hotwordList.querySelectorAll("button[data-hotword-source]")) {
    button.addEventListener("click", async () => {
      await deleteHotword(button.dataset.hotwordSource);
      await loadHotwords();
    });
  }
}

async function handleAddHotword(event) {
  event.preventDefault();
  const source = elements.hotwordSource.value.trim();
  const target = elements.hotwordTarget.value.trim();

  if (!source || !target) {
    elements.hotwordStatus.textContent = "请填写完整";
    return;
  }

  try {
    await createHotword({ source, target });
    elements.hotwordSource.value = "";
    elements.hotwordTarget.value = "";
    await loadHotwords();
    elements.hotwordStatus.textContent = "已添加";
  } catch (error) {
    elements.hotwordStatus.textContent = error.message;
  }
}

async function copyText(text, statusElement = null) {
  if (!text) {
    if (statusElement) {
      statusElement.textContent = "无可复制内容";
    }
    return;
  }

  await navigator.clipboard.writeText(text);
  if (statusElement) {
    statusElement.textContent = "已复制";
  }
}

function sceneLabel(scene) {
  const labels = {
    general: "通用输入",
    meeting: "会议纪要",
    study: "学习笔记",
    message: "聊天回复",
    code_note: "代码说明",
  };
  return labels[scene] ?? scene;
}

function formatFileSize(bytes) {
  if (!bytes) {
    return "0 KB";
  }
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDuration(durationMs) {
  const seconds = Math.max(0, Math.round(durationMs / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes ? `${minutes}m ${rest}s` : `${rest}s`;
}

function providerLabel(provider) {
  return getProviderInfo(provider).label;
}

function setOptionState(select, supportedValues, labels) {
  for (const option of select.options) {
    const supported = supportedValues.includes(option.value);
    option.hidden = !supported;
    option.disabled = !supported;
    option.textContent = supported ? labels[option.value] : `${labels[option.value]}（不支持）`;
  }

  if (select.selectedOptions[0]?.disabled) {
    select.value = supportedValues[0] ?? "";
  }
}

function syncRecognitionControls() {
  syncProviderOptions();

  const provider = getProviderInfo();
  const supportedSources = provider.supported_sources ?? [];
  const supportedLanguages = provider.supported_languages ?? [];
  const supportedModes = provider.supported_modes ?? [];

  setOptionState(elements.sourceSelect, supportedSources, sourceLabels);
  setOptionState(elements.languageSelect, supportedLanguages, languageLabels);
  setOptionState(elements.modeSelect, supportedModes, modeLabels);

  const source = elements.sourceSelect.value;
  const fileMode = source === "file";
  const browserMode = provider.id === "browser";

  elements.sourceSelect.disabled = browserMode || supportedSources.length <= 1;
  elements.modeSelect.disabled = browserMode || supportedModes.length <= 1;
  elements.languageSelect.disabled = supportedLanguages.length <= 1;
  elements.fileField.classList.toggle("hidden", !fileMode);
  elements.saveAudioCheckbox.disabled = browserMode;
  elements.saveAudioHint.textContent = browserMode
    ? "浏览器 Web Speech 不提供音频文件，因此只能保存文本会话。"
    : "开启后，下一次整理文本会把本次音频一起归档到会话库。";
  if (browserMode) {
    elements.saveAudioCheckbox.checked = false;
    clearPendingAudioAttachment();
  }

  if (browserMode) {
    elements.recordButton.textContent = "开始识别";
    setRecognitionHint("本机识别使用浏览器 Web Speech API，支持前端实时临时结果；输入场景会在“整理文本”时生效。");
  } else if (provider.id === "xfyun_iat") {
    elements.recordButton.textContent = pcmStreamRecorder.isRecording()
      ? "停止实时识别"
      : "开始实时识别";
    setRecognitionHint("IAT 用于麦克风或标签页短音频，会通过 WebSocket 实时显示识别中的文本。");
  } else if (fileMode) {
    elements.recordButton.textContent = "上传并识别";
    setRecognitionHint("录音文件转写会上传完整音频并轮询最终结果，适合长音频。");
  } else {
    elements.recordButton.textContent = wavRecorder.isRecording() ? "停止并识别" : "开始录制";
    setRecognitionHint(
      source === "system"
        ? "扬声器音频通过浏览器屏幕/标签页共享采集，停止后上传到录音文件转写接口。"
        : "录制完成后会生成 16k WAV 并上传到所选识别接口。",
    );
  }
}

function setupEventListeners() {
  for (const button of elements.navButtons) {
    button.addEventListener("click", () => setActiveView(button.dataset.viewTarget));
  }
  elements.recordButton.addEventListener("click", handleRecognition);
  elements.sampleButton.addEventListener("click", handleFillSample);
  elements.processButton.addEventListener("click", handleProcessText);
  elements.copyButton.addEventListener("click", handleCopyResult);
  elements.clearButton.addEventListener("click", handleClearText);
  elements.refreshHistoryButton.addEventListener("click", loadHistory);
  elements.clearHistoryButton.addEventListener("click", handleClearHistory);
  elements.historyCategoryFilter.addEventListener("change", handleHistoryFilterChange);
  elements.historyFavoriteFilter.addEventListener("change", handleHistoryFilterChange);
  elements.historySearchInput.addEventListener("input", handleHistorySearchInput);
  elements.categoryForm.addEventListener("submit", handleAddCategory);
  elements.sessionDetailForm.addEventListener("submit", handleSaveSession);
  elements.replaceSessionAudioButton.addEventListener("click", handleReplaceSessionAudio);
  elements.deleteSessionAudioButton.addEventListener("click", handleDeleteSessionAudio);
  elements.copySessionButton.addEventListener("click", () =>
    copyText(elements.sessionProcessedText.value.trim(), elements.sessionDetailStatus),
  );
  elements.sendSessionToWorkbenchButton.addEventListener("click", handleSendSessionToWorkbench);
  elements.deleteSessionButton.addEventListener("click", handleDeleteSelectedSession);
  elements.hotwordForm.addEventListener("submit", handleAddHotword);
  elements.rawText.addEventListener("input", updateMetrics);
  elements.processedText.addEventListener("input", updateMetrics);
  elements.vendorSelect.addEventListener("change", () => {
    resetRecognitionPhase();
    syncProviderOptions();
    syncRecognitionControls();
  });
  elements.providerSelect.addEventListener("change", () => {
    resetRecognitionPhase();
    syncRecognitionControls();
  });
  elements.sourceSelect.addEventListener("change", () => {
    resetRecognitionPhase();
    syncRecognitionControls();
  });
  elements.languageSelect.addEventListener("change", () => {
    resetRecognitionPhase();
    speechController.setLanguage(elements.languageSelect.value);
    syncRecognitionControls();
  });
  elements.modeSelect.addEventListener("change", () => {
    resetRecognitionPhase();
    syncRecognitionControls();
  });
}

function setupSpeechSupport() {
  if (speechController.isSupported()) {
    elements.recordButton.disabled = false;
    return;
  }

  setRecognitionPhase("error", {
    status: "当前浏览器不支持本机语音识别",
    source: "idle",
    transport: "本机不可用",
    detail: "可切换到云端 API，使用录音或音频文件上传识别。",
    level: 0,
  });
}

setupEventListeners();
resetRecognitionPhase();
setupSpeechSupport();
syncVendorOptions();
syncRecognitionControls();
refreshApiStatus();
loadAsrProviders();
loadHotwords();
loadSessionLibrary();
