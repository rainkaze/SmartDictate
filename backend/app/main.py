import asyncio
import shutil
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile
from starlette.responses import FileResponse
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
from backend.app.asr.providers.baidu import (
    BaiduRealtimeStreamingSession,
    validate_baidu_stream_request,
)
from backend.app.asr.providers.registry import AsrProviderRegistry
from backend.app.asr.streaming import IatStreamingSession, validate_iat_stream_request
from backend.app.core.config import get_settings
from backend.app.core.middleware import RequestContextMiddleware
from backend.app.models import (
    HotwordCreateRequest,
    HotwordItem,
    ProcessTranscriptRequest,
    TranscriptCategory,
    TranscriptCategoryCreateRequest,
    TranscriptCategoryUpdateRequest,
    TranscriptItem,
    TranscriptMetadataUpdateRequest,
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

SESSION_AUDIO_DIR = Path("backend/data/session-audio")


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

    if provider not in {AsrProviderName.XFYUN_IAT, AsrProviderName.BAIDU_REALTIME}:
        await websocket.send_json({"type": "error", "message": "当前接口不支持实时流式识别"})
        await websocket.close(code=1008)
        return

    try:
        if provider == AsrProviderName.XFYUN_IAT:
            validate_iat_stream_request(settings, source)
            session = IatStreamingSession(settings=settings, source=source, language=language)
            ready_message = "IAT 实时识别已连接"
        else:
            validate_baidu_stream_request(settings, source)
            session = BaiduRealtimeStreamingSession(
                settings=settings,
                source=source,
                language=language,
            )
            ready_message = "百度实时语音识别已连接"
    except ValueError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1008)
        return

    session.start()
    await websocket.send_json({"type": "ready", "message": ready_message})

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
    if provider == AsrProviderName.BAIDU_REALTIME:
        raise HTTPException(status_code=400, detail="百度实时语音识别请通过实时 WebSocket 接口调用")

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


@app.get("/api/transcript-categories", response_model=list[TranscriptCategory])
def list_transcript_categories() -> list[TranscriptCategory]:
    return store.list_categories()


@app.post(
    "/api/transcript-categories",
    response_model=TranscriptCategory,
    status_code=status.HTTP_201_CREATED,
)
def create_transcript_category(
    payload: TranscriptCategoryCreateRequest,
) -> TranscriptCategory:
    try:
        return store.create_category(payload.name, payload.color)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.patch(
    "/api/transcript-categories/{category_id}",
    response_model=TranscriptCategory,
)
def update_transcript_category(
    category_id: str,
    payload: TranscriptCategoryUpdateRequest,
) -> TranscriptCategory:
    try:
        item = store.update_category(category_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return item


@app.delete(
    "/api/transcript-categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_transcript_category(category_id: str, response: Response) -> None:
    try:
        deleted = store.delete_category(category_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not deleted:
        response.status_code = status.HTTP_404_NOT_FOUND


@app.get("/api/transcripts", response_model=list[TranscriptItem])
def list_transcripts(
    limit: int = Query(default=20, ge=1, le=100),
    category_id: str | None = Query(default=None),
    favorite: bool | None = Query(default=None),
    query: str | None = Query(default=None, max_length=80),
) -> list[TranscriptItem]:
    return store.list_recent(
        limit=limit,
        category_id=category_id,
        favorite=favorite,
        query=query,
    )


@app.patch("/api/transcripts/{transcript_id}", response_model=TranscriptItem)
def update_transcript_metadata(
    transcript_id: str,
    payload: TranscriptMetadataUpdateRequest,
) -> TranscriptItem:
    try:
        item = store.update_metadata(transcript_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")
    return item


@app.post("/api/transcripts/{transcript_id}/audio", response_model=TranscriptItem)
async def upload_transcript_audio(
    transcript_id: str,
    request: Request,
) -> TranscriptItem:
    transcript = store.get(transcript_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")

    try:
        form = await request.form()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail="音频上传接口需要安装 python-multipart，请执行 pip install -r requirements.txt",
        ) from exc

    audio = form.get("audio")
    if not isinstance(audio, UploadFile):
        raise HTTPException(status_code=400, detail="缺少音频文件")

    duration_ms = _parse_optional_int(form.get("duration_ms"))
    SESSION_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    filename = audio.filename or "session-audio.wav"
    suffix = _safe_audio_suffix(filename)
    target_file = SESSION_AUDIO_DIR / f"{transcript_id}-{uuid4().hex}{suffix}"

    old_audio_path = store.get_audio_path(transcript_id)
    try:
        with target_file.open("wb") as target:
            shutil.copyfileobj(audio.file, target)
        item = store.attach_audio(
            transcript_id=transcript_id,
            audio_path=str(target_file),
            filename=filename,
            content_type=audio.content_type or "application/octet-stream",
            size_bytes=target_file.stat().st_size,
            duration_ms=duration_ms,
        )
    finally:
        audio.file.close()

    if item is None:
        _delete_file_if_exists(target_file)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")

    if old_audio_path:
        _delete_file_if_exists(Path(old_audio_path))
    return item


@app.get("/api/transcripts/{transcript_id}/audio")
def get_transcript_audio(transcript_id: str) -> FileResponse:
    item = store.get(transcript_id)
    audio_path = store.get_audio_path(transcript_id)
    if item is None or not item.audio or not audio_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音频不存在")

    audio_file = Path(audio_path)
    if not audio_file.exists():
        store.clear_audio(transcript_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音频文件已丢失")

    return FileResponse(
        audio_file,
        media_type=item.audio.content_type,
        filename=item.audio.filename,
    )


@app.delete("/api/transcripts/{transcript_id}/audio", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcript_audio(transcript_id: str, response: Response) -> None:
    audio_path = store.get_audio_path(transcript_id)
    item = store.clear_audio(transcript_id)
    if item is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return
    if audio_path:
        _delete_file_if_exists(Path(audio_path))


@app.delete("/api/transcripts/{transcript_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcript(transcript_id: str, response: Response) -> None:
    audio_path = store.get_audio_path(transcript_id)
    deleted = store.delete(transcript_id)
    if not deleted:
        response.status_code = status.HTTP_404_NOT_FOUND
        return
    if audio_path:
        _delete_file_if_exists(Path(audio_path))


@app.delete("/api/transcripts", status_code=status.HTTP_204_NO_CONTENT)
def clear_transcripts() -> None:
    audio_paths = store.list_audio_paths()
    store.clear()
    for audio_path in audio_paths:
        _delete_file_if_exists(Path(audio_path))


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


def _safe_audio_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm", ".flac", ".pcm"}:
        return suffix
    return ".wav"


def _parse_optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _delete_file_if_exists(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
