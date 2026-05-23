import {
  checkHealth,
  clearTranscripts,
  createHotword,
  deleteHotword,
  deleteTranscript,
  listHotwords,
  listTranscripts,
  processTranscript,
} from "./modules/api-client.js";
import { createSpeechRecognitionController } from "./modules/speech-recognition.js";
import { escapeHtml } from "./modules/html.js";
import "./styles.css";

const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  sceneSelect: document.querySelector("#sceneSelect"),
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

const sampleText = "嗯 我想用派森开发七牛语音输入法，然后让小七帮我整理文档";

const state = {
  startedAt: null,
  timerId: null,
  historyItems: [],
  hotwordItems: [],
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
  elements.rawText.value = sampleText;
  elements.processedText.value = "";
  elements.copyStatus.textContent = "未复制";
  elements.removedFillers.textContent = "0";
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
            <span>→</span>
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
    code_note: "代码注释",
  };
  return labels[scene] ?? scene;
}

function setupEventListeners() {
  elements.recordButton.addEventListener("click", () => {
    speechController.toggle();
  });
  elements.sampleButton.addEventListener("click", handleFillSample);
  elements.processButton.addEventListener("click", handleProcessText);
  elements.copyButton.addEventListener("click", handleCopyResult);
  elements.clearButton.addEventListener("click", handleClearText);
  elements.refreshHistoryButton.addEventListener("click", loadHistory);
  elements.clearHistoryButton.addEventListener("click", handleClearHistory);
  elements.hotwordForm.addEventListener("submit", handleAddHotword);
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
loadHotwords();
loadHistory();
