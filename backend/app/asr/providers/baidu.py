import base64
import json
import queue
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from backend.app.asr.models import (
    AsrProviderInfo,
    AsrProviderName,
    AsrTranscriptionOptions,
    AsrTranscriptionResult,
    AudioLanguage,
    AudioSource,
    RecognitionMode,
)
from backend.app.asr.providers.base import AsrProvider
from backend.app.asr.streaming import QueueAudioStream
from backend.app.core.config import Settings

BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_SHORT_ASR_URL = "http://vop.baidu.com/server_api"
BAIDU_REALTIME_ASR_URL = "wss://vop.baidu.com/realtime_asr"
BAIDU_REALTIME_FRAME_BYTES = 5120


class BaiduProvider(AsrProvider):
    def __init__(self, settings: Settings, provider_name: AsrProviderName) -> None:
        self.settings = settings
        self.provider_name = provider_name
        self._token_client = _BaiduAccessTokenClient(settings)

    def info(self) -> AsrProviderInfo:
        enabled = self._is_configured()

        if self.provider_name == AsrProviderName.BAIDU_REALTIME:
            return AsrProviderInfo(
                id=self.provider_name,
                label="百度实时语音识别",
                enabled=enabled,
                description="百度 WebSocket 实时语音识别，适合麦克风或标签页音频实时转写。",
                supported_sources=[AudioSource.MICROPHONE, AudioSource.SYSTEM],
                supported_languages=[
                    AudioLanguage.ZH_CN,
                    AudioLanguage.ZH_EN,
                    AudioLanguage.EN_US,
                    AudioLanguage.DIALECT,
                ],
                supported_modes=[RecognitionMode.REALTIME],
                reason=(
                    None
                    if enabled
                    else "缺少 BAIDU_ASR_APP_ID、BAIDU_ASR_API_KEY 或 BAIDU_ASR_SECRET_KEY"
                ),
            )

        return AsrProviderInfo(
            id=self.provider_name,
            label="百度短语音识别",
            enabled=enabled,
            description="百度短语音 REST API，适合 60 秒以内录音或本机短音频文件。",
            supported_sources=[AudioSource.MICROPHONE, AudioSource.FILE, AudioSource.SYSTEM],
            supported_languages=[
                AudioLanguage.ZH_CN,
                AudioLanguage.ZH_EN,
                AudioLanguage.EN_US,
                AudioLanguage.DIALECT,
            ],
            supported_modes=[RecognitionMode.SHORT],
            reason=(
                None
                if enabled
                else "缺少 BAIDU_ASR_APP_ID、BAIDU_ASR_API_KEY 或 BAIDU_ASR_SECRET_KEY"
            ),
        )

    def transcribe(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        if not self._is_configured():
            raise RuntimeError(
                "百度语音识别未配置，请先设置 "
                "BAIDU_ASR_APP_ID、BAIDU_ASR_API_KEY、BAIDU_ASR_SECRET_KEY"
            )
        if self.provider_name == AsrProviderName.BAIDU_REALTIME:
            raise RuntimeError("百度实时语音识别请通过 WebSocket 实时接口调用。")

        return self._transcribe_short(audio_file, options)

    def _is_configured(self) -> bool:
        return all(
            (
                self.settings.baidu_asr_app_id,
                self.settings.baidu_asr_api_key,
                self.settings.baidu_asr_secret_key,
            )
        )

    def _transcribe_short(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        started_at = time.perf_counter()
        audio_data = audio_file.read_bytes()
        if not audio_data:
            raise RuntimeError("百度短语音识别失败：音频文件为空。")

        payload = {
            "format": _audio_format(audio_file),
            "rate": 16000,
            "dev_pid": _short_dev_pid(options.language),
            "channel": 1,
            "token": self._token_client.get_token(),
            "cuid": "smartdictate-server",
            "len": len(audio_data),
            "speech": base64.b64encode(audio_data).decode("utf-8"),
        }

        try:
            with httpx.Client(timeout=self.settings.baidu_asr_request_timeout) as client:
                response = client.post(
                    BAIDU_SHORT_ASR_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"百度短语音识别 HTTP 请求失败：{exc.response.text}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"百度短语音识别网络请求失败：{exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("百度短语音识别返回了无法解析的 JSON。") from exc

        err_no = int(data.get("err_no", -1))
        if err_no != 0:
            raise RuntimeError(_friendly_baidu_response_error(data))

        segments = [str(item) for item in data.get("result", []) if str(item)]
        return AsrTranscriptionResult(
            provider=self.provider_name,
            source=options.source,
            language=options.language,
            mode=RecognitionMode.SHORT,
            raw_text="".join(segments).strip(),
            segments=segments,
            duration_ms=round((time.perf_counter() - started_at) * 1000),
            metadata={
                "engine": "baidu_short_asr",
                "dev_pid": payload["dev_pid"],
                "sn": data.get("sn"),
                "corpus_no": data.get("corpus_no"),
            },
        )


class BaiduRealtimeStreamingSession:
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
            import websocket
        except ImportError:
            self.events.put(
                {
                    "type": "error",
                    "message": "缺少 websocket-client 依赖，请先安装 requirements.txt",
                }
            )
            self.events.put({"type": "done"})
            return

        sn = str(uuid4())
        uri = f"{BAIDU_REALTIME_ASR_URL}?sn={sn}"
        sender_done = threading.Event()
        accumulator = _BaiduRealtimeTranscriptAccumulator()
        ws = None

        try:
            ws = websocket.create_connection(
                uri,
                timeout=self.settings.baidu_asr_realtime_idle_timeout,
            )
            ws.send(json.dumps(self._start_frame()), opcode=websocket.ABNF.OPCODE_TEXT)

            sender = threading.Thread(
                target=self._send_audio_frames,
                args=(ws, websocket, sender_done),
                daemon=True,
            )
            sender.start()
            self.events.put({"type": "ready", "message": "百度实时语音识别已连接"})

            idle_deadline = time.monotonic() + self.settings.baidu_asr_realtime_idle_timeout
            while True:
                try:
                    message = ws.recv()
                except websocket.WebSocketTimeoutException:
                    if sender_done.is_set() and time.monotonic() > idle_deadline:
                        break
                    continue
                except websocket.WebSocketConnectionClosedException:
                    break

                if not message:
                    break
                idle_deadline = time.monotonic() + self.settings.baidu_asr_realtime_idle_timeout
                event = self._parse_message(message, accumulator)
                if event:
                    self.events.put(event)

            self.events.put(
                {
                    "type": "final",
                    "provider": AsrProviderName.BAIDU_REALTIME,
                    "source": self.source,
                    "language": self.language,
                    "mode": RecognitionMode.REALTIME,
                    "text": accumulator.text.strip(),
                    "duration_ms": round((time.perf_counter() - self._started_at) * 1000),
                }
            )
        except Exception as exc:
            self.events.put({"type": "error", "message": _friendly_baidu_stream_error(exc)})
        finally:
            try:
                if ws is not None:
                    ws.close()
            except Exception:
                pass
            self.events.put({"type": "done"})

    def _start_frame(self) -> dict[str, Any]:
        dev_pid = _realtime_dev_pid(self.language)
        try:
            appid = int(self.settings.baidu_asr_app_id)
        except ValueError as exc:
            raise RuntimeError("BAIDU_ASR_APP_ID 必须是百度控制台中的数字 AppID。") from exc
        data: dict[str, Any] = {
            "appid": appid,
            "appkey": self.settings.baidu_asr_api_key,
            "dev_pid": dev_pid,
            "cuid": "smartdictate-server",
            "format": "pcm",
            "sample": 16000,
        }
        if dev_pid == 15376:
            data["user"] = "smartdictate"
        return {"type": "START", "data": data}

    def _send_audio_frames(
        self,
        ws: Any,
        websocket_module: Any,
        sender_done: threading.Event,
    ) -> None:
        try:
            while True:
                chunk = self.audio_stream.read(BAIDU_REALTIME_FRAME_BYTES)
                if not chunk:
                    break
                ws.send(chunk, opcode=websocket_module.ABNF.OPCODE_BINARY)
            ws.send(json.dumps({"type": "FINISH"}), opcode=websocket_module.ABNF.OPCODE_TEXT)
        finally:
            sender_done.set()

    def _parse_message(
        self,
        message: str | bytes,
        accumulator: "_BaiduRealtimeTranscriptAccumulator",
    ) -> dict[str, Any] | None:
        if isinstance(message, bytes):
            message = message.decode("utf-8", errors="ignore")
        payload = json.loads(message)
        payload_type = payload.get("type")
        if payload_type == "HEARTBEAT":
            return None

        err_no = int(payload.get("err_no", 0))
        if err_no != 0:
            return {"type": "error", "message": _friendly_baidu_response_error(payload)}

        result = str(payload.get("result") or "")
        if payload_type == "MID_TEXT":
            text = accumulator.update_partial(result)
            return {
                "type": "partial",
                "provider": AsrProviderName.BAIDU_REALTIME,
                "source": self.source,
                "language": self.language,
                "mode": RecognitionMode.REALTIME,
                "text": text,
                "segment": result,
                "metadata": {"sn": payload.get("sn"), "log_id": payload.get("log_id")},
            }

        if payload_type == "FIN_TEXT":
            text = accumulator.add_final(result)
            return {
                "type": "partial",
                "provider": AsrProviderName.BAIDU_REALTIME,
                "source": self.source,
                "language": self.language,
                "mode": RecognitionMode.REALTIME,
                "text": text,
                "segment": result,
                "metadata": {
                    "sn": payload.get("sn"),
                    "log_id": payload.get("log_id"),
                    "start_time": payload.get("start_time"),
                    "end_time": payload.get("end_time"),
                },
            }

        return None


class _BaiduAccessTokenClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token = ""
        self._expires_at = 0.0

    def get_token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token

        try:
            with httpx.Client(timeout=self.settings.baidu_asr_request_timeout) as client:
                response = client.post(
                    BAIDU_TOKEN_URL,
                    params={
                        "grant_type": "client_credentials",
                        "client_id": self.settings.baidu_asr_api_key,
                        "client_secret": self.settings.baidu_asr_secret_key,
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"百度 access_token 获取失败：{exc.response.text}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"百度 access_token 网络请求失败：{exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("百度 access_token 返回了无法解析的 JSON。") from exc

        if data.get("error"):
            description = data.get("error_description") or data.get("error")
            raise RuntimeError(f"百度 access_token 鉴权失败：{description}")

        token = str(data.get("access_token") or "")
        if not token:
            raise RuntimeError("百度 access_token 响应缺少 access_token。")

        expires_in = int(data.get("expires_in") or 0)
        self._token = token
        self._expires_at = now + max(expires_in, 60)
        return token


class _BaiduRealtimeTranscriptAccumulator:
    def __init__(self) -> None:
        self._final_segments: list[str] = []
        self._partial = ""

    @property
    def text(self) -> str:
        return "".join(self._final_segments) + self._partial

    def update_partial(self, text: str) -> str:
        self._partial = text
        return self.text

    def add_final(self, text: str) -> str:
        if text:
            self._final_segments.append(text)
        self._partial = ""
        return self.text


def validate_baidu_stream_request(settings: Settings, source: AudioSource) -> None:
    if source == AudioSource.FILE:
        raise ValueError("百度实时语音识别仅支持麦克风或标签页音频，不支持本机文件上传。")
    if not (
        settings.baidu_asr_app_id
        and settings.baidu_asr_api_key
        and settings.baidu_asr_secret_key
    ):
        raise ValueError(
            "百度实时语音识别未配置，请先设置 "
            "BAIDU_ASR_APP_ID、BAIDU_ASR_API_KEY、BAIDU_ASR_SECRET_KEY"
        )


def _audio_format(audio_file: Path) -> str:
    suffix = audio_file.suffix.lower().lstrip(".")
    if suffix in {"pcm", "wav", "amr", "m4a"}:
        return suffix
    return "wav"


def _short_dev_pid(language: AudioLanguage) -> int:
    if language == AudioLanguage.EN_US:
        return 1737
    if language == AudioLanguage.DIALECT:
        return 1637
    return 1537


def _realtime_dev_pid(language: AudioLanguage) -> int:
    if language == AudioLanguage.EN_US:
        return 17372
    if language == AudioLanguage.DIALECT:
        return 15376
    return 15372


def _friendly_baidu_response_error(data: dict[str, Any]) -> str:
    err_no = data.get("err_no")
    err_msg = data.get("err_msg") or data.get("err_msg".replace("_", "")) or data
    sn = data.get("sn")
    suffix = f"，sn={sn}" if sn else ""
    return f"百度语音识别失败：{err_msg}（err_no={err_no}{suffix}）"


def _friendly_baidu_stream_error(exc: Exception) -> str:
    message = str(exc)
    lower_message = message.lower()
    if "handshake" in lower_message or "401" in lower_message or "403" in lower_message:
        return "百度实时语音识别连接鉴权失败，请检查 AppID、API Key 和服务权限。"
    if "timed out" in lower_message or "timeout" in lower_message:
        return "百度实时语音识别连接超时，请检查网络或稍后重试。"
    return f"百度实时语音识别失败：{message}"
