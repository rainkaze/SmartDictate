import queue
import threading
import time
from typing import Any

from backend.app.asr.models import (
    AsrProviderName,
    AudioLanguage,
    AudioSource,
    RecognitionMode,
)
from backend.app.asr.providers.xfyun import (
    _extract_text,
    _friendly_xfyun_error,
    _IatTranscriptAccumulator,
)
from backend.app.core.config import Settings


class QueueAudioStream:
    def __init__(self) -> None:
        self._chunks: queue.Queue[bytes | None] = queue.Queue()
        self._buffer = bytearray()
        self._closed = False

    def write(self, chunk: bytes) -> None:
        if self._closed:
            return
        self._chunks.put(chunk)

    def read(self, size: int = -1) -> bytes:
        while not self._buffer and not self._closed:
            chunk = self._chunks.get()
            if chunk is None:
                self._closed = True
                break
            self._buffer.extend(chunk)

        if not self._buffer:
            return b""

        if size < 0 or size >= len(self._buffer):
            data = bytes(self._buffer)
            self._buffer.clear()
            return data

        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def close(self) -> None:
        if self._closed:
            return
        self._chunks.put(None)


class IatStreamingSession:
    def __init__(
        self,
        settings: Settings,
        source: AudioSource,
        language: AudioLanguage,
    ) -> None:
        self.settings = settings
        self.source = source
        self.language = language
        self.audio_stream = QueueAudioStream()
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._started_at = time.perf_counter()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def write_audio(self, chunk: bytes) -> None:
        self.audio_stream.write(chunk)

    def close_audio(self) -> None:
        self.audio_stream.close()

    def next_event(self, timeout: float = 0.5) -> dict[str, Any] | None:
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None

    def _run(self) -> None:
        try:
            from xfyunsdkspeech.iat_client import IatClient
        except ImportError:
            self.events.put(
                {
                    "type": "error",
                    "message": "缺少 xfyunsdkspeech 依赖，请先安装 requirements.txt",
                }
            )
            self.events.put({"type": "done"})
            return

        accumulator = _IatTranscriptAccumulator()
        try:
            client = IatClient(
                app_id=self.settings.xfyun_app_id,
                api_key=self.settings.xfyun_api_key,
                api_secret=self.settings.xfyun_api_secret,
                language=_iat_language(self.language),
                accent=_iat_accent(self.language),
                domain="iat",
                format="audio/L16;rate=16000",
                encoding="raw",
                dwa="wpgs",
                ptt=1,
                vinfo=0,
                frame_size=1280,
                request_timeout=self.settings.xfyun_request_timeout,
            )
            for chunk in client.stream(self.audio_stream):
                text = _extract_text(chunk)
                if not text:
                    continue
                accumulator.update(chunk, text)
                self.events.put(
                    {
                        "type": "partial",
                        "provider": AsrProviderName.XFYUN_IAT,
                        "source": self.source,
                        "language": self.language,
                        "mode": RecognitionMode.REALTIME,
                        "text": accumulator.text.strip(),
                        "segment": text,
                    }
                )
            self.events.put(
                {
                    "type": "final",
                    "provider": AsrProviderName.XFYUN_IAT,
                    "source": self.source,
                    "language": self.language,
                    "mode": RecognitionMode.REALTIME,
                    "text": accumulator.text.strip(),
                    "duration_ms": round((time.perf_counter() - self._started_at) * 1000),
                }
            )
        except Exception as exc:
            self.events.put({"type": "error", "message": _friendly_xfyun_error(exc)})
        finally:
            self.events.put({"type": "done"})


def validate_iat_stream_request(settings: Settings, source: AudioSource) -> None:
    if source == AudioSource.FILE:
        raise ValueError("IAT 实时流式识别仅支持麦克风或标签页音频，不支持本机文件上传。")
    if not (
        settings.xfyun_app_id
        and settings.xfyun_api_key
        and settings.xfyun_api_secret
    ):
        raise ValueError(
            "讯飞语音听写未配置，请先设置 "
            "XFYUN_APP_ID、XFYUN_API_KEY、XFYUN_API_SECRET"
        )


def _iat_language(language: AudioLanguage) -> str:
    if language in {AudioLanguage.EN_US, AudioLanguage.JA_JP}:
        return "en_us" if language == AudioLanguage.EN_US else "ja_jp"
    return "zh_cn"


def _iat_accent(language: AudioLanguage) -> str:
    return "mandarin" if language != AudioLanguage.DIALECT else "lmz"
