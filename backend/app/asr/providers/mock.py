import time
from pathlib import Path

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


class BrowserProvider(AsrProvider):
    def info(self) -> AsrProviderInfo:
        return AsrProviderInfo(
            id=AsrProviderName.BROWSER,
            label="本机浏览器识别",
            enabled=True,
            description="使用浏览器 Web Speech API，免费、低配置，但专业术语准确率有限。",
            supported_sources=[AudioSource.MICROPHONE],
            supported_languages=[AudioLanguage.ZH_CN, AudioLanguage.ZH_EN, AudioLanguage.EN_US],
            supported_modes=[RecognitionMode.REALTIME],
        )

    def transcribe(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        raise NotImplementedError("浏览器识别在前端完成，不经过后端转写接口。")


class FutureProvider(AsrProvider):
    def info(self) -> AsrProviderInfo:
        return AsrProviderInfo(
            id=AsrProviderName.FUTURE,
            label="待扩展识别 API",
            enabled=False,
            description="预留给后续接入其他云厂商或本地模型。",
            supported_sources=[AudioSource.MICROPHONE, AudioSource.FILE, AudioSource.SYSTEM],
            supported_languages=[
                AudioLanguage.ZH_CN,
                AudioLanguage.ZH_EN,
                AudioLanguage.EN_US,
                AudioLanguage.JA_JP,
                AudioLanguage.DIALECT,
                AudioLanguage.OTHER,
            ],
            supported_modes=[RecognitionMode.SHORT, RecognitionMode.REALTIME, RecognitionMode.LONG],
            reason="尚未配置具体实现",
        )

    def transcribe(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        started_at = time.perf_counter()
        return AsrTranscriptionResult(
            provider=AsrProviderName.FUTURE,
            source=options.source,
            language=options.language,
            mode=options.mode,
            raw_text="",
            duration_ms=round((time.perf_counter() - started_at) * 1000),
            metadata={"error": "future provider is not implemented"},
        )
