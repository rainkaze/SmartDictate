from abc import ABC, abstractmethod
from pathlib import Path

from backend.app.asr.models import AsrProviderInfo, AsrTranscriptionOptions, AsrTranscriptionResult


class AsrProvider(ABC):
    @abstractmethod
    def info(self) -> AsrProviderInfo:
        """Return frontend-facing provider capabilities."""

    @abstractmethod
    def transcribe(
        self,
        audio_file: Path,
        options: AsrTranscriptionOptions,
    ) -> AsrTranscriptionResult:
        """Transcribe an audio file."""

