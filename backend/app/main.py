from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.core.middleware import RequestContextMiddleware
from backend.app.models import (
    HotwordCreateRequest,
    HotwordItem,
    ProcessTranscriptRequest,
    TranscriptItem,
)
from backend.app.services.hotwords import HotwordDictionary
from backend.app.services.text_processor import TextProcessor
from backend.app.services.transcript_store import TranscriptStore

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
app.add_middleware(RequestContextMiddleware)

hotword_dictionary = HotwordDictionary(database_file=settings.database_file)
processor = TextProcessor(rules_provider=hotword_dictionary.get_text_rules)
store = TranscriptStore(database_file=settings.database_file)


@app.get("/api/health")
def health_check() -> dict[str, object]:
    database_ready = store.ping() and hotword_dictionary.ping()
    return {
        "status": "ok" if database_ready else "degraded",
        "version": settings.app_version,
        "storage": {
            "engine": "sqlite",
            "ready": database_ready,
            "transcript_count": store.count(),
            "custom_hotword_count": hotword_dictionary.count_custom(),
        },
    }


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
def list_transcripts(limit: int = Query(default=10, ge=1, le=30)) -> list[TranscriptItem]:
    return store.list_recent(limit=limit)


@app.delete("/api/transcripts/{transcript_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcript(transcript_id: str, response: Response) -> None:
    deleted = store.delete(transcript_id)
    if not deleted:
        response.status_code = status.HTTP_404_NOT_FOUND


@app.delete("/api/transcripts", status_code=status.HTTP_204_NO_CONTENT)
def clear_transcripts() -> None:
    store.clear()


@app.get("/api/hotwords", response_model=list[HotwordItem])
def list_hotwords() -> list[HotwordItem]:
    return hotword_dictionary.list_items()


@app.post("/api/hotwords", response_model=HotwordItem, status_code=status.HTTP_201_CREATED)
def create_hotword(payload: HotwordCreateRequest) -> HotwordItem:
    try:
        return hotword_dictionary.add(payload.source, payload.target)
    except ValueError as exc:
        status_code = status.HTTP_400_BAD_REQUEST
        if str(exc) == "热词已存在":
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.delete("/api/hotwords/{source}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hotword(source: str, response: Response) -> None:
    deleted = hotword_dictionary.delete(source)
    if not deleted:
        response.status_code = status.HTTP_404_NOT_FOUND
