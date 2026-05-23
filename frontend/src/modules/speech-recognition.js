const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

const errorMessages = {
  "not-allowed": "麦克风权限被拒绝，请在浏览器地址栏允许麦克风权限",
  "no-speech": "没有检测到语音，请靠近麦克风后重试",
  "audio-capture": "没有找到可用麦克风，请检查设备连接",
  network: "语音识别网络异常，请稍后重试",
};

export function createSpeechRecognitionController(callbacks) {
  let recognition = null;
  let recording = false;

  function isSupported() {
    return Boolean(SpeechRecognition);
  }

  function ensureRecognition() {
    if (!isSupported()) {
      return null;
    }

    if (recognition) {
      return recognition;
    }

    recognition = new SpeechRecognition();
    recognition.lang = "zh-CN";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      let finalText = "";
      let interimText = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0].transcript.trim();
        if (event.results[index].isFinal) {
          finalText += transcript;
        } else {
          interimText += transcript;
        }
      }

      if (finalText) {
        callbacks.onFinalText(finalText);
      }
      callbacks.onInterimText(interimText);
    };

    recognition.onerror = (event) => {
      recording = false;
      callbacks.onError(errorMessages[event.error] ?? `语音识别失败：${event.error}`);
    };

    recognition.onend = () => {
      if (recording) {
        recognition.start();
        return;
      }
      callbacks.onStop();
    };

    return recognition;
  }

  function start() {
    const currentRecognition = ensureRecognition();
    if (!currentRecognition || recording) {
      return;
    }

    recording = true;
    callbacks.onStart();
    currentRecognition.start();
  }

  function stop() {
    if (!recognition || !recording) {
      return;
    }

    recording = false;
    recognition.stop();
  }

  function toggle() {
    if (recording) {
      stop();
    } else {
      start();
    }
  }

  return {
    isSupported,
    start,
    stop,
    toggle,
  };
}
