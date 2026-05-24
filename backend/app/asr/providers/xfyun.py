import base64
import hashlib
import hmac
import json
import secrets
import string
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

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
from backend.app.core.config import Settings

XFYUN_LARGE_BASE_URL = "https://office-api-ist-dx.iflyaisol.com"
XFYUN_LARGE_UPLOAD_PATH = "/v2/upload"
XFYUN_LARGE_RESULT_PATH = "/v2/getResult"


class XfyunProvider(AsrProvider):
    def __init__(self, settings: Settings, provider_name: AsrProviderName) -> None:
        self.settings = settings
        self.provider_name = provider_name

    def info(self) -> AsrProviderInfo:
        enabled = self._is_configured()

        if self.provider_name == AsrProviderName.XFYUN_IAT:
            return AsrProviderInfo(
                id=self.provider_name,
                label="科大讯飞语音听写 IAT",
                enabled=enabled,
                description="短音频流式听写，适合一句话、短录音和快速试音。",
                supported_sources=[AudioSource.MICROPHONE, AudioSource.SYSTEM],
                supported_languages=[
                    AudioLanguage.ZH_CN,
                    AudioLanguage.ZH_EN,
                    AudioLanguage.EN_US,
                    AudioLanguage.JA_JP,
                    AudioLanguage.DIALECT,
                ],
                supported_modes=[RecognitionMode.SHORT],
                reason=None if enabled else "缺少 XFYUN_APP_ID、XFYUN_API_KEY 或 XFYUN_API_SECRET",
            )

        return AsrProviderInfo(
            id=self.provider_name,
            label="科大讯飞录音文件转写大模型",
            enabled=enabled,
            description="大模型录音文件转写，上传完整音频后轮询获取最终文本。",
            supported_sources=[AudioSource.MICROPHONE, AudioSource.FILE, AudioSource.SYSTEM],
            supported_languages=[AudioLanguage.ZH_CN, AudioLanguage.ZH_EN, AudioLanguage.DIALECT],
            supported_modes=[RecognitionMode.LONG],
            reason=None if enabled else "缺少 XFYUN_APP_ID、XFYUN_API_KEY 或 XFYUN_API_SECRET",
        )

    def transcribe(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        if not self._is_configured():
            raise RuntimeError(
                "讯飞语音识别未配置，请先设置 "
                "XFYUN_APP_ID、XFYUN_API_KEY、XFYUN_API_SECRET"
            )

        if self.provider_name == AsrProviderName.XFYUN_LFASR_LARGE:
            return self._transcribe_large_file(audio_file, options)

        if options.source == AudioSource.FILE:
            raise RuntimeError(
                "讯飞语音听写 IAT 仅支持麦克风或标签页音频短录制，"
                "不支持本机文件上传。"
            )

        return self._transcribe_iat(audio_file, options)

    def _is_configured(self) -> bool:
        return all(
            (
                self.settings.xfyun_app_id,
                self.settings.xfyun_api_key,
                self.settings.xfyun_api_secret,
            )
        )

    def _transcribe_iat(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        started_at = time.perf_counter()
        try:
            from xfyunsdkspeech.iat_client import IatClient
        except ImportError as exc:
            raise RuntimeError("缺少 xfyunsdkspeech 依赖，请先安装 requirements.txt") from exc

        client = IatClient(
            app_id=self.settings.xfyun_app_id,
            api_key=self.settings.xfyun_api_key,
            api_secret=self.settings.xfyun_api_secret,
            language=self._iat_language(options.language),
            accent=self._iat_accent(options.language),
            domain="iat",
            format=self._audio_format(audio_file),
            encoding="raw",
            dwa="wpgs",
            ptt=1,
            vinfo=0,
            request_timeout=self.settings.xfyun_request_timeout,
        )

        chunks: list[str] = []
        accumulator = _IatTranscriptAccumulator()
        try:
            with audio_file.open("rb") as stream:
                for chunk in client.stream(stream):
                    text = _extract_text(chunk)
                    if text:
                        chunks.append(text)
                        accumulator.update(chunk, text)
        except Exception as exc:
            raise RuntimeError(_friendly_xfyun_error(exc)) from exc

        return AsrTranscriptionResult(
            provider=self.provider_name,
            source=options.source,
            language=options.language,
            mode=RecognitionMode.SHORT,
            raw_text=accumulator.text.strip(),
            segments=chunks,
            duration_ms=round((time.perf_counter() - started_at) * 1000),
            metadata={"engine": "iat"},
        )

    def _transcribe_large_file(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        started_at = time.perf_counter()
        file_size = audio_file.stat().st_size
        if file_size <= 0:
            raise RuntimeError("讯飞录音文件转写大模型失败：音频文件为空。")

        client = _XfyunLargeFileClient(self.settings)
        signature_random = _random_signature_value()

        upload_data = client.upload(audio_file, options, signature_random)
        if upload_data.get("code") != "000000":
            raise RuntimeError(_friendly_large_response_error("上传", upload_data))

        order_id = upload_data["content"]["orderId"]
        result_data: dict[str, Any] = {}
        for _ in range(self.settings.xfyun_file_max_polls):
            time.sleep(self.settings.xfyun_file_poll_interval)
            result_data = client.get_result(order_id, signature_random)
            if result_data.get("code") != "000000":
                raise RuntimeError(_friendly_large_response_error("查询", result_data))

            order_info = result_data.get("content", {}).get("orderInfo", {})
            status = int(order_info.get("status", 0))
            if status == 4:
                break
            if status == -1:
                raise RuntimeError(_friendly_large_response_error("转写", result_data))
        else:
            raise RuntimeError(f"讯飞录音文件转写大模型超时，orderId={order_id}")

        order_result = result_data["content"].get("orderResult", "[]")
        segments = _extract_order_result_segments(order_result)
        return AsrTranscriptionResult(
            provider=self.provider_name,
            source=options.source,
            language=options.language,
            mode=RecognitionMode.LONG,
            raw_text="".join(segments).strip(),
            segments=segments,
            duration_ms=round((time.perf_counter() - started_at) * 1000),
            metadata={"engine": "xfyun_lfasr_large", "order_id": order_id},
        )

    def _iat_language(self, language: AudioLanguage) -> str:
        if language in {AudioLanguage.EN_US, AudioLanguage.JA_JP}:
            return "en_us" if language == AudioLanguage.EN_US else "ja_jp"
        return "zh_cn"

    def _iat_accent(self, language: AudioLanguage) -> str:
        return "mandarin" if language != AudioLanguage.DIALECT else "lmz"

    def _audio_format(self, audio_file: Path) -> str:
        suffix = audio_file.suffix.lower()
        if suffix in {".wav", ".pcm"}:
            return "audio/L16;rate=16000"
        return "audio/L16;rate=16000"


class _XfyunLargeFileClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def upload(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
        signature_random: str,
    ) -> dict[str, Any]:
        path = XFYUN_LARGE_UPLOAD_PATH
        params = {
            "appId": self.settings.xfyun_app_id,
            "accessKeyId": self.settings.xfyun_api_key,
            "fileName": audio_file.name,
            "fileSize": str(audio_file.stat().st_size),
            "durationCheckDisable": "true",
            "language": _large_file_language(options.language),
            "audioMode": "fileStream",
            "standardWav": "1" if audio_file.suffix.lower() == ".wav" else "0",
            "resultType": "transfer",
            "signatureRandom": signature_random,
        }
        with audio_file.open("rb") as stream:
            return self._post(path, params, content=stream.read())

    def get_result(self, order_id: str, signature_random: str) -> dict[str, Any]:
        params = {
            "accessKeyId": self.settings.xfyun_api_key,
            "orderId": order_id,
            "resultType": "transfer",
            "signatureRandom": signature_random,
        }
        return self._post(XFYUN_LARGE_RESULT_PATH, params, content=b"")

    def _post(self, path: str, params: dict[str, str], content: bytes) -> dict[str, Any]:
        signed_params = dict(params)
        signed_params["dateTime"] = _xfyun_datetime()
        signed_params["signature"] = _large_file_signature(
            signed_params,
            self.settings.xfyun_api_secret,
        )
        url = f"{XFYUN_LARGE_BASE_URL}{path}"
        try:
            content_type = "application/octet-stream" if content else "application/json"
            signature = signed_params.pop("signature")
            with httpx.Client(timeout=self.settings.xfyun_request_timeout) as client:
                response = client.post(
                    url,
                    params=signed_params,
                    content=content,
                    headers={
                        "Content-Type": content_type,
                        "signature": signature,
                    },
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"讯飞大模型转写 HTTP 请求失败：{exc.response.text}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"讯飞大模型转写网络请求失败：{exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("讯飞大模型转写返回了无法解析的 JSON") from exc


class _IatTranscriptAccumulator:
    def __init__(self) -> None:
        self._parts: list[str] = []
        self._fallback_text = ""

    @property
    def text(self) -> str:
        if self._parts:
            return "".join(self._parts)
        return self._fallback_text

    def update(self, chunk: Any, text: str) -> None:
        result = _extract_result(chunk)
        if isinstance(result, dict):
            pgs = result.get("pgs")
            rg = result.get("rg")
            if pgs == "rpl" and isinstance(rg, list) and len(rg) == 2:
                self._replace_range(rg, text)
                return
            if pgs == "apd":
                self._append_or_replace_progressive(text)
                return

        if self._parts:
            self._append_or_replace_progressive(text)
            return

        self._fallback_text = _merge_incremental_text(self._fallback_text, text)

    def _append_or_replace_progressive(self, text: str) -> None:
        if not self._parts:
            self._parts.append(text)
            return

        last = self._parts[-1]
        if text.startswith(last) or last.startswith(text) or _has_meaningful_overlap(last, text):
            self._parts[-1] = _merge_incremental_text(last, text)
            return

        self._parts.append(text)

    def _replace_range(self, rg: list[Any], text: str) -> None:
        try:
            start = max(int(rg[0]) - 1, 0)
            end = max(int(rg[1]), start)
        except (TypeError, ValueError):
            self._parts.append(text)
            return

        if start >= len(self._parts):
            self._parts.append(text)
            return

        self._parts[start:end] = [text]


def _extract_result(chunk: Any) -> Any:
    if isinstance(chunk, str):
        try:
            chunk = json.loads(chunk)
        except json.JSONDecodeError:
            return None

    if not isinstance(chunk, dict):
        return None

    return chunk.get("result", chunk)


def _extract_text(chunk: Any) -> str:
    if isinstance(chunk, str):
        try:
            chunk = json.loads(chunk)
        except json.JSONDecodeError:
            return chunk

    if not isinstance(chunk, dict):
        return ""

    result = _extract_result(chunk)
    words = result.get("ws", []) if isinstance(result, dict) else []
    pieces: list[str] = []
    for word in words:
        candidates = word.get("cw", []) if isinstance(word, dict) else []
        if candidates:
            pieces.append(str(candidates[0].get("w", "")))
    if pieces:
        return "".join(pieces)

    for key in ("text", "sentence", "onebest", "dst"):
        value = chunk.get(key)
        if isinstance(value, str):
            return value

    return ""


def _merge_incremental_text(current: str, incoming: str) -> str:
    """Merge streaming ASR partials without duplicating progressive hypotheses."""
    if not incoming:
        return current
    if not current:
        return incoming
    if incoming.startswith(current):
        return incoming
    if current.startswith(incoming):
        return current

    max_overlap = min(len(current), len(incoming))
    for size in range(max_overlap, 0, -1):
        if current[-size:] == incoming[:size]:
            return current + incoming[size:]

    return current + incoming


def _has_meaningful_overlap(left: str, right: str) -> bool:
    max_overlap = min(len(left), len(right))
    for size in range(max_overlap, 1, -1):
        if left[-size:] == right[:size]:
            return True
    return False


def _extract_order_result_segments(order_result: str) -> list[str]:
    try:
        data = json.loads(order_result)
    except json.JSONDecodeError:
        return [order_result]

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("lattice", [])
    else:
        items = []
    segments: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("onebest"), str):
            segments.append(item["onebest"])
            continue
        json_1best = item.get("json_1best")
        if isinstance(json_1best, str):
            segments.append(_extract_json_1best_text(json_1best))

    return [segment for segment in segments if segment]


def _extract_json_1best_text(json_1best: str) -> str:
    try:
        data = json.loads(json_1best)
    except json.JSONDecodeError:
        return json_1best

    words: list[str] = []
    for rt in data.get("st", {}).get("rt", []):
        for ws in rt.get("ws", []):
            candidates = ws.get("cw", [])
            if candidates:
                words.append(str(candidates[0].get("w", "")))
    return "".join(words)


def _large_file_language(language: AudioLanguage) -> str:
    if language == AudioLanguage.ZH_EN:
        return "autodialect"
    if language == AudioLanguage.DIALECT:
        return "autodialect"
    return "zh_cn"


def _xfyun_datetime() -> str:
    china_timezone = timezone(timedelta(hours=8))
    return datetime.now(china_timezone).strftime("%Y-%m-%dT%H:%M:%S%z")


def _random_signature_value() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _large_file_signature(params: dict[str, str], api_secret: str) -> str:
    base_string = "&".join(
        f"{key}={quote_plus(str(params[key]))}"
        for key in sorted(params)
        if key != "signature" and params[key] not in (None, "")
    )
    digest = hmac.new(
        api_secret.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _friendly_large_response_error(stage: str, data: dict[str, Any]) -> str:
    description = str(data.get("descInfo") or data.get("desc") or data.get("message") or data)
    code = str(data.get("code", ""))
    if code in {"26625", "26600"} or "时长不足" in description:
        return f"讯飞录音文件转写大模型{stage}失败：{description}"
    if "sign" in description.lower() or "signature" in description.lower():
        return (
            f"讯飞录音文件转写大模型{stage}鉴权失败：{description}。"
            "请确认 XFYUN_API_KEY 和 XFYUN_API_SECRET 来自大模型转写页面同一个应用。"
        )
    return f"讯飞录音文件转写大模型{stage}失败: {data}"


def _friendly_xfyun_error(exc: Exception) -> str:
    message = str(exc)
    lower_message = message.lower()
    if "apikey not found" in lower_message:
        return (
            "讯飞鉴权失败：APIKey 不存在或不属于当前语音识别服务。"
            "请确认 XFYUN_API_KEY 是控制台 APIKey，XFYUN_API_SECRET 是 APISecret。"
        )
    if "401" in message or "unauthorized" in lower_message:
        return "讯飞鉴权失败：请检查 APP_ID、APIKey、APISecret 是否来自同一个已开通的语音识别应用。"
    return f"讯飞语音识别失败：{message}"
