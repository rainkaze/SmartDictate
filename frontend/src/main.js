import {
  checkHealth,
  clearTranscripts,
  createHotword,
  deleteHotword,
  deleteTranscript,
  listAsrProviders,
  listHotwords,
  listTranscripts,
  processTranscript,
  transcribeAudio,
} from "./modules/api-client.js";
import { createWavRecorder } from "./modules/audio-recorder.js";
import { escapeHtml } from "./modules/html.js";
import { createSpeechRecognitionController } from "./modules/speech-recognition.js";
import "./styles.css";

const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  sceneSelect: document.querySelector("#sceneSelect"),
  vendorSelect: document.querySelector("#vendorSelect"),
  apiField: document.querySelector("#apiField"),
  providerSelect: document.querySelector("#providerSelect"),
  sourceSelect: document.querySelector("#sourceSelect"),
  languageSelect: document.querySelector("#languageSelect"),
  modeSelect: document.querySelector("#modeSelect"),
  fileField: document.querySelector("#fileField"),
  audioFileInput: document.querySelector("#audioFileInput"),
  recordButton: document.querySelector("#recordButton"),
  sampleButton: document.querySelector("#sampleButton"),
  processButton: document.querySelector("#processButton"),
  copyButton: document.querySelector("#copyButton"),
  clearButton: document.querySelector("#clearButton"),
  refreshHistoryButton: document.querySelector("#refreshHistoryButton"),
  clearHistoryButton: document.querySelector("#clearHistoryButton"),
  hotwordForm: document.querySelector("#hotwordForm"),
  hotwordSource: document.querySelector("#hotwordSource"),
  hotwordTarget: document.querySelector("#hotwordTarget"),
  hotwordStatus: document.querySelector("#hotwordStatus"),
  hotwordList: document.querySelector("#hotwordList"),
  recognitionStatus: document.querySelector("#recognitionStatus"),
  interimText: document.querySelector("#interimText"),
  copyStatus: document.querySelector("#copyStatus"),
  rawText: document.querySelector("#rawText"),
  processedText: document.querySelector("#processedText"),
  rawLength: document.querySelector("#rawLength"),
  processedLength: document.querySelector("#processedLength"),
  removedFillers: document.querySelector("#removedFillers"),
  elapsedSeconds: document.querySelector("#elapsedSeconds"),
  historyList: document.querySelector("#historyList"),
};

const sampleText =
  "嗯我想用 SmartDictate 整理二叉树的遍历笔记，二叉树的遍历包括前序遍历、中序遍历、后序遍历以及层序遍历。";

const state = {
  startedAt: null,
  timerId: null,
  historyItems: [],
  hotwordItems: [],
  asrProviders: [],
};

const providerFallbacks = {
  browser: {
    id: "browser",
    label: "浏览器 Web Speech API",
    enabled: true,
    supported_sources: ["microphone"],
    supported_languages: ["zh_cn", "zh_en", "en_us", "ja_jp"],
    supported_modes: ["realtime"],
  },
  xfyun_iat: {
    id: "xfyun_iat",
    label: "语音听写 IAT",
    enabled: false,
    supported_sources: ["microphone", "file", "system"],
    supported_languages: ["zh_cn", "zh_en", "en_us", "ja_jp", "dialect"],
    supported_modes: ["short"],
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
  baidu: [],
  future: [],
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
  other: "其他 / 待扩展",
};

const modeLabels = {
  short: "短音频听写",
  realtime: "实时转写",
  long: "录音文件转写",
};

const wavRecorder = createWavRecorder();

const speechController = createSpeechRecognitionController({
  onStart: () => {
    state.startedAt = Date.now();
    startElapsedTimer();
    elements.recordButton.textContent = "停止识别";
    elements.recordButton.classList.add("recording");
    elements.recognitionStatus.textContent = "浏览器正在监听";
    elements.interimText.textContent = "请开始说话。";
  },
  onStop: () => {
    stopElapsedTimer();
    elements.recordButton.textContent = "开始识别";
    elements.recordButton.classList.remove("recording");
    elements.recognitionStatus.textContent = "已停止";
    elements.interimText.textContent = "浏览器识别已停止。";
  },
  onFinalText: (text) => {
    appendRawText(text);
    updateMetrics();
  },
  onInterimText: (text) => {
    elements.interimText.textContent = text || "正在等待更清晰的语音输入。";
  },
  onError: (message) => {
    stopElapsedTimer();
    elements.recognitionStatus.textContent = message;
    elements.recordButton.textContent = "开始识别";
    elements.recordButton.classList.remove("recording");
  },
});

function setApiStatus(online) {
  elements.apiStatus.textContent = online ? "后端在线" : "后端离线";
  elements.apiStatus.classList.toggle("offline", !online);
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
    } else if (option.value === "baidu") {
      option.disabled = true;
      option.textContent = "百度 API（未配置）";
    } else {
      option.disabled = true;
      option.textContent = "待扩展 API（未配置）";
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
    speechController.toggle(elements.languageSelect.value);
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

async function startApiRecording(source) {
  try {
    state.startedAt = Date.now();
    startElapsedTimer();
    await wavRecorder.start(source);
    elements.recordButton.textContent = "停止并识别";
    elements.recordButton.classList.add("recording");
    elements.recognitionStatus.textContent =
      source === "system" ? "正在采集扬声器音频" : "正在录制麦克风";
    elements.interimText.textContent =
      source === "system"
        ? "请选择要共享音频的标签页或窗口，停止后会上传识别。"
        : "录制完成后会上传到所选识别 API。";
  } catch (error) {
    stopElapsedTimer();
    elements.recordButton.classList.remove("recording");
    elements.recordButton.textContent = "开始识别";
    elements.recognitionStatus.textContent = error.message;
  }
}

async function stopApiRecordingAndTranscribe() {
  elements.recordButton.disabled = true;
  elements.recognitionStatus.textContent = "正在上传识别";

  try {
    const recording = await wavRecorder.stop();
    elements.recordButton.classList.remove("recording");
    elements.recordButton.textContent = "开始识别";
    if (!recording || recording.blob.size === 0) {
      elements.recognitionStatus.textContent = "没有采集到音频";
      return;
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
    elements.recognitionStatus.textContent = "请先选择本机音频文件";
    return;
  }

  state.startedAt = Date.now();
  startElapsedTimer();
  elements.recordButton.disabled = true;
  elements.recognitionStatus.textContent = "正在上传音频文件";

  try {
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
    elements.recognitionStatus.textContent = result.raw_text ? "识别完成" : "识别完成但未返回文本";
    elements.interimText.textContent = `识别接口：${providerLabel(result.provider)}，耗时 ${result.duration_ms}ms`;
  } catch (error) {
    setApiStatus(error instanceof TypeError ? false : true);
    elements.recognitionStatus.textContent = error.message;
    elements.interimText.textContent = "后端已返回识别错误，请按提示检查 API 凭据、服务权限或音频格式。";
  }
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
  stopElapsedTimer();
  updateMetrics();
}

function handleFillSample() {
  replaceRawText(sampleText);
  elements.recognitionStatus.textContent = "已填入示例";
  elements.interimText.textContent = "可以直接点击“整理文本”验证前后端联动。";
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
    state.historyItems = await listTranscripts({ limit: 10 });
    renderHistory(state.historyItems);
    setApiStatus(true);
  } catch {
    elements.historyList.innerHTML = '<p class="history-time">启动后端后可查看历史记录。</p>';
    setApiStatus(false);
  }
}

function renderHistory(items) {
  if (!items.length) {
    elements.historyList.innerHTML = '<p class="history-time">暂无记录。</p>';
    return;
  }

  elements.historyList.innerHTML = items.map(renderHistoryItem).join("");

  for (const button of elements.historyList.querySelectorAll("button[data-action]")) {
    button.addEventListener("click", () => {
      handleHistoryAction(button.dataset.action, button.dataset.historyId);
    });
  }
}

function renderHistoryItem(item) {
  const time = new Date(item.created_at).toLocaleString();
  return `
    <article class="history-item">
      <p class="history-text">${escapeHtml(item.processed_text)}</p>
      <div class="history-meta">
        <span>${time}</span>
        <span>${sceneLabel(item.scene)}</span>
        <span>${item.metrics.processed_length} 字</span>
      </div>
      <div class="history-actions">
        <button class="secondary-button" type="button" data-action="fill" data-history-id="${item.id}">填入</button>
        <button class="secondary-button" type="button" data-action="copy" data-history-id="${item.id}">复制</button>
        <button class="text-button danger-text" type="button" data-action="delete" data-history-id="${item.id}">删除</button>
      </div>
    </article>
  `;
}

async function handleHistoryAction(action, id) {
  const item = state.historyItems.find((entry) => entry.id === id);
  if (!item) {
    return;
  }

  if (action === "fill") {
    elements.processedText.value = item.processed_text;
    updateMetrics();
    return;
  }

  if (action === "copy") {
    await copyText(item.processed_text);
    return;
  }

  if (action === "delete") {
    await deleteTranscript(id);
    await loadHistory();
  }
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
  await loadHistory();
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

function providerLabel(provider) {
  return getProviderInfo(provider).label;
}

function setOptionState(select, supportedValues, labels) {
  for (const option of select.options) {
    const supported = supportedValues.includes(option.value);
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

  if (browserMode) {
    elements.recordButton.textContent = "开始识别";
    elements.interimText.textContent =
      "本机识别使用浏览器 Web Speech API，支持前端实时临时结果；输入场景会在“整理文本”时生效。";
  } else if (provider.id === "xfyun_iat") {
    elements.recordButton.textContent = fileMode ? "上传并识别" : "开始录制";
    elements.interimText.textContent =
      "当前 IAT 通过后端 SDK 消费流式结果，前端暂不实时显示；录制停止后返回最终文本。";
  } else if (fileMode) {
    elements.recordButton.textContent = "上传并识别";
    elements.interimText.textContent = "录音文件转写会上传完整音频并轮询最终结果，适合长音频。";
  } else {
    elements.recordButton.textContent = wavRecorder.isRecording() ? "停止并识别" : "开始录制";
    elements.interimText.textContent =
      source === "system"
        ? "扬声器音频通过浏览器屏幕/标签页共享采集，停止后上传到录音文件转写接口。"
        : "录制完成后会生成 16k WAV 并上传到所选识别接口。";
  }
}

function setupEventListeners() {
  elements.recordButton.addEventListener("click", handleRecognition);
  elements.sampleButton.addEventListener("click", handleFillSample);
  elements.processButton.addEventListener("click", handleProcessText);
  elements.copyButton.addEventListener("click", handleCopyResult);
  elements.clearButton.addEventListener("click", handleClearText);
  elements.refreshHistoryButton.addEventListener("click", loadHistory);
  elements.clearHistoryButton.addEventListener("click", handleClearHistory);
  elements.hotwordForm.addEventListener("submit", handleAddHotword);
  elements.rawText.addEventListener("input", updateMetrics);
  elements.processedText.addEventListener("input", updateMetrics);
  elements.vendorSelect.addEventListener("change", () => {
    syncProviderOptions();
    syncRecognitionControls();
  });
  elements.providerSelect.addEventListener("change", syncRecognitionControls);
  elements.sourceSelect.addEventListener("change", syncRecognitionControls);
  elements.languageSelect.addEventListener("change", () => {
    speechController.setLanguage(elements.languageSelect.value);
  });
  elements.modeSelect.addEventListener("change", syncRecognitionControls);
}

function setupSpeechSupport() {
  if (speechController.isSupported()) {
    elements.recordButton.disabled = false;
    return;
  }

  elements.recognitionStatus.textContent = "当前浏览器不支持本机语音识别";
  elements.interimText.textContent = "可切换到云端 API，使用录音或音频文件上传识别。";
}

setupEventListeners();
setupSpeechSupport();
syncVendorOptions();
syncRecognitionControls();
refreshApiStatus();
loadAsrProviders();
loadHotwords();
loadHistory();
