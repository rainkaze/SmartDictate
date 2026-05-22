from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models import ProcessTranscriptRequest, TranscriptItem
from backend.app.services.storage import TranscriptStore
from backend.app.services.text_processor import TextProcessor

app = FastAPI(
    title="SmartDictate API",
    description="Local backend for voice transcription cleanup and history.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

processor = TextProcessor()
store = TranscriptStore()


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
