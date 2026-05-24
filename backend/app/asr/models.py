from enum import StrEnum

from pydantic import BaseModel, Field


class AsrProviderName(StrEnum):
    BROWSER = "browser"
    XFYUN_IAT = "xfyun_iat"
    XFYUN_LFASR_LARGE = "xfyun_lfasr_large"
    FUTURE = "future"


class AudioSource(StrEnum):
    MICROPHONE = "microphone"
    SYSTEM = "system"
    FILE = "file"


class AudioLanguage(StrEnum):
    ZH_CN = "zh_cn"
    ZH_EN = "zh_en"
    EN_US = "en_us"
    JA_JP = "ja_jp"
    DIALECT = "dialect"
    OTHER = "other"


class RecognitionMode(StrEnum):
    SHORT = "short"
    REALTIME = "realtime"
    LONG = "long"


class AsrProviderInfo(BaseModel):
    id: AsrProviderName
    label: str
    enabled: bool
    description: str
    supported_sources: list[AudioSource]
    supported_languages: list[AudioLanguage]
    supported_modes: list[RecognitionMode]
    reason: str | None = None


class AsrTranscriptionOptions(BaseModel):
    provider: AsrProviderName = AsrProviderName.XFYUN_IAT
    source: AudioSource = AudioSource.MICROPHONE
    language: AudioLanguage = AudioLanguage.ZH_EN
    mode: RecognitionMode = RecognitionMode.SHORT


class AsrTranscriptionResult(BaseModel):
    provider: AsrProviderName
    source: AudioSource
    language: AudioLanguage
    mode: RecognitionMode
    raw_text: str = Field(default="")
    segments: list[str] = Field(default_factory=list)
    duration_ms: int
    metadata: dict[str, object] = Field(default_factory=dict)
