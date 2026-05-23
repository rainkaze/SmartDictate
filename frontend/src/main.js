import { checkHealth, listTranscripts, processTranscript } from "./modules/api-client.js";
import { createSpeechRecognitionController } from "./modules/speech-recognition.js";
import { escapeHtml } from "./modules/html.js";
import "./styles.css";

const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  sceneSelect: document.querySelector("#sceneSelect"),
  recordButton: document.querySelector("#recordButton"),
  processButton: document.querySelector("#processButton"),
  copyButton: document.querySelector("#copyButton"),
  clearButton: document.querySelector("#clearButton"),
  refreshHistoryButton: document.querySelector("#refreshHistoryButton"),
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

const state = {
  startedAt: null,
  timerId: null,
};

const speechController = createSpeechRecognitionController({
  onStart: () => {
    state.startedAt = Date.now();
    startElapsedTimer();
    elements.recordButton.textContent = "停止语音输入";
    elements.recordButton.classList.add("recording");
    elements.recognitionStatus.textContent = "正在聆听";
    elements.interimText.textContent = "请开始说话。";
  },
  onStop: () => {
    stopElapsedTimer();
    elements.recordButton.textContent = "开始语音输入";
    elements.recordButton.classList.remove("recording");
    elements.recognitionStatus.textContent = "已停止";
    elements.interimText.textContent = "临时识别结果会显示在这里。";
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
    elements.recordButton.textContent = "开始语音输入";
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

function appendRawText(text) {
  const current = elements.rawText.value.trim();
  elements.rawText.value = current ? `${current} ${text}` : text;
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
  const text = elements.processedText.value.trim();
  if (!text) {
    elements.copyStatus.textContent = "无可复制内容";
    return;
  }

  await navigator.clipboard.writeText(text);
  elements.copyStatus.textContent = "已复制";
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
    const items = await listTranscripts();
    renderHistory(items);
  } catch {
    elements.historyList.innerHTML = '<p class="history-time">启动后端后可查看历史记录。</p>';
  }
}

function renderHistory(items) {
  if (!items.length) {
    elements.historyList.innerHTML = '<p class="history-time">暂无记录。</p>';
    return;
  }

  elements.historyList.innerHTML = items
    .map((item) => {
      const time = new Date(item.created_at).toLocaleString();
      return `
        <article class="history-item">
          <p class="history-text">${escapeHtml(item.processed_text)}</p>
          <span class="history-time">${time} · ${sceneLabel(item.scene)}</span>
          <button class="secondary-button" type="button" data-history-id="${item.id}">填入结果</button>
        </article>
      `;
    })
    .join("");

  for (const button of elements.historyList.querySelectorAll("button[data-history-id]")) {
    button.addEventListener("click", () => {
      const item = items.find((entry) => entry.id === button.dataset.historyId);
      if (item) {
        elements.processedText.value = item.processed_text;
        updateMetrics();
      }
    });
  }
}

function sceneLabel(scene) {
  const labels = {
    general: "通用输入",
    meeting: "会议纪要",
    study: "学习笔记",
    message: "聊天回复",
    code_note: "代码注释",
  };
  return labels[scene] ?? scene;
}

function setupEventListeners() {
  elements.recordButton.addEventListener("click", () => {
    speechController.toggle();
  });
  elements.processButton.addEventListener("click", handleProcessText);
  elements.copyButton.addEventListener("click", handleCopyResult);
  elements.clearButton.addEventListener("click", handleClearText);
  elements.refreshHistoryButton.addEventListener("click", loadHistory);
  elements.rawText.addEventListener("input", updateMetrics);
  elements.processedText.addEventListener("input", updateMetrics);
}

function setupSpeechSupport() {
  if (speechController.isSupported()) {
    elements.recordButton.disabled = false;
    return;
  }

  elements.recordButton.disabled = true;
  elements.recognitionStatus.textContent = "当前浏览器不支持语音识别";
  elements.interimText.textContent = "建议使用最新版 Chrome 或 Edge，并通过本地开发地址访问页面。";
}

setupEventListeners();
setupSpeechSupport();
refreshApiStatus();
loadHistory();
