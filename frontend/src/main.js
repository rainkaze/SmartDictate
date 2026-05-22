import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  sceneSelect: document.querySelector("#sceneSelect"),
  recordButton: document.querySelector("#recordButton"),
  processButton: document.querySelector("#processButton"),
  copyButton: document.querySelector("#copyButton"),
  refreshHistoryButton: document.querySelector("#refreshHistoryButton"),
  recognitionStatus: document.querySelector("#recognitionStatus"),
  copyStatus: document.querySelector("#copyStatus"),
  rawText: document.querySelector("#rawText"),
  processedText: document.querySelector("#processedText"),
  rawLength: document.querySelector("#rawLength"),
  processedLength: document.querySelector("#processedLength"),
  removedFillers: document.querySelector("#removedFillers"),
  elapsedSeconds: document.querySelector("#elapsedSeconds"),
  historyList: document.querySelector("#historyList"),
};

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isRecording = false;
let startedAt = null;

function setApiStatus(online) {
  elements.apiStatus.textContent = online ? "后端在线" : "后端离线";
  elements.apiStatus.classList.toggle("offline", !online);
}

async function checkApi() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    setApiStatus(response.ok);
  } catch {
    setApiStatus(false);
  }
}

function setupRecognition() {
  if (!SpeechRecognition) {
    elements.recordButton.disabled = true;
    elements.recognitionStatus.textContent = "当前浏览器不支持语音识别";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = "zh-CN";
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    let finalText = "";
    let interimText = "";

    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = event.results[index][0].transcript;
      if (event.results[index].isFinal) {
        finalText += transcript;
      } else {
        interimText += transcript;
      }
    }

    if (finalText) {
      elements.rawText.value = `${elements.rawText.value}${finalText} `;
      updateMetrics();
    }

    elements.recognitionStatus.textContent = interimText ? `识别中：${interimText}` : "正在聆听";
  };

  recognition.onerror = (event) => {
    elements.recognitionStatus.textContent = `识别失败：${event.error}`;
    stopRecording();
  };

  recognition.onend = () => {
    if (isRecording) {
      recognition.start();
    }
  };
}

function startRecording() {
  if (!recognition) {
    return;
  }

  isRecording = true;
  startedAt = Date.now();
  elements.recordButton.textContent = "停止语音输入";
  elements.recordButton.classList.add("recording");
  elements.recognitionStatus.textContent = "正在聆听";
  recognition.start();
}

function stopRecording() {
  if (!recognition) {
    return;
  }

  isRecording = false;
  elements.recordButton.textContent = "开始语音输入";
  elements.recordButton.classList.remove("recording");
  elements.recognitionStatus.textContent = "已停止";
  recognition.stop();
  updateMetrics();
}

async function processText() {
  const rawText = elements.rawText.value.trim();
  if (!rawText) {
    elements.recognitionStatus.textContent = "请先输入文本";
    return;
  }

  elements.processButton.disabled = true;
  elements.processButton.textContent = "整理中";

  try {
    const response = await fetch(`${API_BASE_URL}/api/transcripts/process`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        raw_text: rawText,
        scene: elements.sceneSelect.value,
      }),
    });

    if (!response.ok) {
      throw new Error("process failed");
    }

    const item = await response.json();
    elements.processedText.value = item.processed_text;
    renderMetrics(item.metrics);
    await loadHistory();
  } catch {
    elements.recognitionStatus.textContent = "后端不可用，请先启动 FastAPI 服务";
    setApiStatus(false);
  } finally {
    elements.processButton.disabled = false;
    elements.processButton.textContent = "整理文本";
  }
}

async function copyResult() {
  const text = elements.processedText.value.trim();
  if (!text) {
    elements.copyStatus.textContent = "无可复制内容";
    return;
  }

  await navigator.clipboard.writeText(text);
  elements.copyStatus.textContent = "已复制";
}

function updateMetrics() {
  elements.rawLength.textContent = String(elements.rawText.value.length);
  elements.processedLength.textContent = String(elements.processedText.value.length);
  if (startedAt) {
    elements.elapsedSeconds.textContent = `${Math.max(0, Math.round((Date.now() - startedAt) / 1000))}s`;
  }
}

function renderMetrics(metrics) {
  elements.rawLength.textContent = String(metrics.raw_length);
  elements.processedLength.textContent = String(metrics.processed_length);
  elements.removedFillers.textContent = String(metrics.removed_fillers);
}

async function loadHistory() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/transcripts`);
    if (!response.ok) {
      throw new Error("history failed");
    }
    const items = await response.json();
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
          <span class="history-time">${time} · ${item.scene}</span>
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

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

elements.recordButton.addEventListener("click", () => {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});
elements.processButton.addEventListener("click", processText);
elements.copyButton.addEventListener("click", copyResult);
elements.refreshHistoryButton.addEventListener("click", loadHistory);
elements.rawText.addEventListener("input", updateMetrics);
elements.processedText.addEventListener("input", updateMetrics);

setupRecognition();
checkApi();
loadHistory();
