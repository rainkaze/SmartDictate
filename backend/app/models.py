from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Scene = Literal["general", "meeting", "study", "message", "code_note"]


def derive_transcript_title(text: str, fallback: str = "未命名会话") -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return fallback
    return normalized[:40]


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


class TranscriptCategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=24)
    color: str = Field(default="#0f766e", pattern=r"^#[0-9A-Fa-f]{6}$")


class TranscriptCategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=24)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class TranscriptCategory(BaseModel):
    id: str
    name: str
    color: str
    sort_order: int
    builtin: bool = False
    created_at: datetime
    updated_at: datetime


class TranscriptMetrics(BaseModel):
    raw_length: int
    processed_length: int
    removed_fillers: int
    estimated_reading_seconds: int


class TranscriptMetadataUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    category_id: str | None = Field(default=None, max_length=64)
    favorite: bool | None = None


class TranscriptItem(BaseModel):
    id: str
    title: str
    raw_text: str
    processed_text: str
    scene: Scene
    category_id: str | None = None
    favorite: bool = False
    metrics: TranscriptMetrics
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        raw_text: str,
        processed_text: str,
        scene: Scene,
        metrics: TranscriptMetrics,
    ) -> "TranscriptItem":
        now = datetime.now(UTC)
        return cls(
            id=str(uuid4()),
            title=derive_transcript_title(processed_text or raw_text),
            raw_text=raw_text,
            processed_text=processed_text,
            scene=scene,
            category_id=None,
            favorite=False,
            metrics=metrics,
            created_at=now,
            updated_at=now,
        )
