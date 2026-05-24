const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export async function listAsrProviders() {
  const response = await fetch(`${API_BASE_URL}/api/asr/providers`);

  if (!response.ok) {
    throw new Error("语音识别工具接口请求失败");
  }

  return response.json();
}

export async function transcribeAudio({ audioBlob, filename, provider, source, language, mode }) {
  const formData = new FormData();
  formData.append("audio", audioBlob, filename);
  formData.append("provider", provider);
  formData.append("source", source);
  formData.append("language", language);
  formData.append("mode", mode);

  const response = await fetch(`${API_BASE_URL}/api/asr/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let message = "语音识别接口请求失败";
    try {
      const payload = await response.json();
      message = payload.detail ?? message;
    } catch {
      // Keep the default message when the backend returns a non-JSON error.
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export function createAsrStreamUrl({ provider, source, language }) {
  const query = new URLSearchParams({ provider, source, language });
  return `${WS_BASE_URL}/api/asr/stream?${query.toString()}`;
}

export async function processTranscript({ rawText, scene }) {
  const response = await fetch(`${API_BASE_URL}/api/transcripts/process`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      raw_text: rawText,
      scene,
    }),
  });

  if (!response.ok) {
    throw new Error("文本整理接口请求失败");
  }

  return response.json();
}

export async function listTranscripts({ limit = 10 } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  const response = await fetch(`${API_BASE_URL}/api/transcripts?${query.toString()}`);

  if (!response.ok) {
    throw new Error("历史记录接口请求失败");
  }

  return response.json();
}

export async function deleteTranscript(id) {
  const response = await fetch(`${API_BASE_URL}/api/transcripts/${id}`, {
    method: "DELETE",
  });

  if (!response.ok && response.status !== 404) {
    throw new Error("删除历史记录失败");
  }
}

export async function clearTranscripts() {
  const response = await fetch(`${API_BASE_URL}/api/transcripts`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("清空历史记录失败");
  }
}

export async function listHotwords() {
  const response = await fetch(`${API_BASE_URL}/api/hotwords`);

  if (!response.ok) {
    throw new Error("热词字典接口请求失败");
  }

  return response.json();
}

export async function createHotword({ source, target }) {
  const response = await fetch(`${API_BASE_URL}/api/hotwords`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ source, target }),
  });

  if (response.status === 409) {
    throw new Error("该识别词已经存在");
  }

  if (!response.ok) {
    throw new Error("添加热词失败");
  }

  return response.json();
}

export async function deleteHotword(source) {
  const response = await fetch(`${API_BASE_URL}/api/hotwords/${encodeURIComponent(source)}`, {
    method: "DELETE",
  });

  if (!response.ok && response.status !== 404) {
    throw new Error("删除热词失败");
  }
}
