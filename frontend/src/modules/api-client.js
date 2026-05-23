const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
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
