from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Scene = Literal["general", "meeting", "study", "message", "code_note"]


class ProcessTranscriptRequest(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=10000)
    scene: Scene = "general"


class HotwordCreateRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=80)
    target: str = Field(..., min_length=1, max_length=80)


class HotwordItem(BaseModel):
    source: str
    target: str
    builtin: bool = False


class TranscriptMetrics(BaseModel):
    raw_length: int
    processed_length: int
    removed_fillers: int
    estimated_reading_seconds: int


class TranscriptItem(BaseModel):
    id: str
    raw_text: str
    processed_text: str
    scene: Scene
    metrics: TranscriptMetrics
    created_at: datetime

    @classmethod
    def create(
        cls,
        raw_text: str,
        processed_text: str,
        scene: Scene,
        metrics: TranscriptMetrics,
    ) -> "TranscriptItem":
        return cls(
            id=str(uuid4()),
            raw_text=raw_text,
            processed_text=processed_text,
            scene=scene,
            metrics=metrics,
            created_at=datetime.now(UTC),
        )
