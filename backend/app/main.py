import asyncio
import shutil
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile
from starlette.websockets import WebSocketDisconnect

from backend.app.asr.models import (
    AsrProviderInfo,
    AsrProviderName,
    AsrTranscriptionOptions,
    AsrTranscriptionResult,
    AudioLanguage,
    AudioSource,
    RecognitionMode,
)
from backend.app.asr.providers.registry import AsrProviderRegistry
from backend.app.asr.streaming import IatStreamingSession, validate_iat_stream_request
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
asr_registry = AsrProviderRegistry(settings)


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


@app.get("/api/asr/providers", response_model=list[AsrProviderInfo])
def list_asr_providers() -> list[AsrProviderInfo]:
    return [provider.info() for provider in asr_registry.list()]


@app.websocket("/api/asr/stream")
async def stream_asr(
    websocket: WebSocket,
    provider: Annotated[AsrProviderName, Query()] = AsrProviderName.XFYUN_IAT,
    source: Annotated[AudioSource, Query()] = AudioSource.MICROPHONE,
    language: Annotated[AudioLanguage, Query()] = AudioLanguage.ZH_EN,
) -> None:
    await websocket.accept()

    if provider != AsrProviderName.XFYUN_IAT:
        await websocket.send_json({"type": "error", "message": "当前仅支持 IAT 实时流式识别"})
        await websocket.close(code=1008)
        return

    try:
        validate_iat_stream_request(settings, source)
    except ValueError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1008)
        return

    session = IatStreamingSession(settings=settings, source=source, language=language)
    session.start()
    await websocket.send_json({"type": "ready", "message": "IAT 实时识别已连接"})

    async def receive_audio() -> None:
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                audio = message.get("bytes")
                if audio:
                    session.write_audio(audio)
                    continue
                text = message.get("text")
                if text == "stop":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            session.close_audio()

    async def send_events() -> None:
        try:
            while True:
                event = await asyncio.to_thread(session.next_event)
                if event is None:
                    continue
                if event.get("type") == "done":
                    break
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass

    await asyncio.gather(receive_audio(), send_events())
    try:
        await websocket.close()
    except RuntimeError:
        pass


@app.post("/api/asr/transcribe", response_model=AsrTranscriptionResult)
async def transcribe_audio(
    request: Request,
) -> AsrTranscriptionResult:
    try:
        form = await request.form()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail="语音上传接口需要安装 python-multipart，请执行 pip install -r requirements.txt",
        ) from exc

    audio = form.get("audio")
    if not isinstance(audio, UploadFile):
        raise HTTPException(status_code=400, detail="缺少音频文件")

    provider = AsrProviderName(str(form.get("provider", AsrProviderName.XFYUN_IAT)))
    source = AudioSource(str(form.get("source", AudioSource.MICROPHONE)))
    language = AudioLanguage(str(form.get("language", AudioLanguage.ZH_EN)))
    mode = RecognitionMode(str(form.get("mode", RecognitionMode.SHORT)))

    if provider == AsrProviderName.BROWSER:
        raise HTTPException(status_code=400, detail="浏览器识别在前端完成，不支持后端上传转写")
    if provider == AsrProviderName.FUTURE:
        raise HTTPException(status_code=501, detail="该识别工具尚未实现")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    audio_file = upload_dir / f"{uuid4()}{suffix.lower()}"

    try:
        with audio_file.open("wb") as target:
            shutil.copyfileobj(audio.file, target)

        options = AsrTranscriptionOptions(
            provider=provider,
            source=source,
            language=language,
            mode=mode,
        )
        return asr_registry.get(provider).transcribe(audio_file, options)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"语音识别失败：{exc}") from exc
    finally:
        audio.file.close()
        if audio_file.exists():
            audio_file.unlink()


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
