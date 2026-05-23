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

export async function listTranscripts() {
  const response = await fetch(`${API_BASE_URL}/api/transcripts`);

  if (!response.ok) {
    throw new Error("历史记录接口请求失败");
  }

  return response.json();
}
