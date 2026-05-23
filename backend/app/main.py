from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.models import ProcessTranscriptRequest, TranscriptItem
from backend.app.services.storage import TranscriptStore
from backend.app.services.text_processor import TextProcessor

settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    description="SmartDictate 本地后端服务，负责文本整理、热词纠错和历史记录。",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

processor = TextProcessor()
store = TranscriptStore(data_file=settings.data_file)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/transcripts/process", response_model=TranscriptItem)
def process_transcript(payload: ProcessTranscriptRequest) -> TranscriptItem:
    result = processor.process(payload.raw_text, payload.scene)
    item = TranscriptItem.create(
        raw_text=payload.raw_text,
        processed_text=result.text,
        scene=payload.scene,
        metrics=result.metrics,
    )
    store.add(item)
    return item


@app.get("/api/transcripts", response_model=list[TranscriptItem])
def list_transcripts() -> list[TranscriptItem]:
    return store.list_recent()
