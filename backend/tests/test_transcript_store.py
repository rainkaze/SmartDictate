import pytest
from backend.app.models import TranscriptItem, TranscriptMetrics
from backend.app.services.transcript_store import MEMORY_DATABASE, TranscriptStore


def create_item(text: str) -> TranscriptItem:
    return TranscriptItem.create(
        raw_text=text,
        processed_text=f"{text}。",
        scene="general",
        metrics=TranscriptMetrics(
            raw_length=len(text),
            processed_length=len(text) + 1,
            removed_fillers=0,
            estimated_reading_seconds=1,
        ),
    )


def create_store(limit: int = 10) -> TranscriptStore:
    return TranscriptStore(database_file=MEMORY_DATABASE, limit=limit)


def test_store_adds_new_item_first() -> None:
    store = create_store()

    first = create_item("第一条")
    second = create_item("第二条")
    store.add(first)
    store.add(second)

    items = store.list_recent()

    assert [item.id for item in items] == [second.id, first.id]
    assert items[0].title == "第二条。"
    assert items[0].favorite is False
    assert items[0].category_id is None


def test_store_limits_query_without_deleting_sessions() -> None:
    store = create_store(limit=3)

    for index in range(5):
        store.add(create_item(f"第{index}条"))

    assert len(store.list_recent()) == 3
    assert len(store.list_recent(limit=2)) == 2
    assert store.count() == 5


def test_store_updates_favorite_title_and_category() -> None:
    store = create_store()
    item = create_item("会议讨论项目排期")
    store.add(item)

    updated = store.update_metadata(
        item.id,
        {
            "title": "项目排期会议",
            "favorite": True,
            "category_id": "meeting",
        },
    )

    assert updated is not None
    assert updated.title == "项目排期会议"
    assert updated.favorite is True
    assert updated.category_id == "meeting"
    assert updated.updated_at >= updated.created_at


def test_store_updates_session_text_and_metrics() -> None:
    store = create_store()
    item = create_item("原始文本")
    store.add(item)

    updated = store.update_metadata(
        item.id,
        {
            "raw_text": "新的原始文本",
            "processed_text": "新的整理结果",
            "scene": "meeting",
        },
    )

    assert updated is not None
    assert updated.raw_text == "新的原始文本"
    assert updated.processed_text == "新的整理结果"
    assert updated.scene == "meeting"
    assert updated.metrics.raw_length == len("新的原始文本")
    assert updated.metrics.processed_length == len("新的整理结果")


def test_store_attaches_and_clears_audio_metadata() -> None:
    store = create_store()
    item = create_item("带音频的会话")
    store.add(item)

    updated = store.attach_audio(
        transcript_id=item.id,
        audio_path="backend/data/session-audio/example.wav",
        filename="example.wav",
        content_type="audio/wav",
        size_bytes=128,
        duration_ms=3000,
    )

    assert updated is not None
    assert updated.audio is not None
    assert updated.audio.filename == "example.wav"
    assert updated.audio.content_type == "audio/wav"
    assert updated.audio.size_bytes == 128
    assert updated.audio.duration_ms == 3000
    assert store.get_audio_path(item.id) == "backend/data/session-audio/example.wav"
    assert store.list_audio_paths() == ["backend/data/session-audio/example.wav"]

    cleared = store.clear_audio(item.id)

    assert cleared is not None
    assert cleared.audio is None
    assert store.get_audio_path(item.id) is None


def test_store_filters_by_category_favorite_and_query() -> None:
    store = create_store()
    meeting = create_item("会议需要确认上线计划")
    study = create_item("学习笔记记录动态规划")
    store.add(meeting)
    store.add(study)
    store.update_metadata(meeting.id, {"category_id": "meeting", "favorite": True})
    store.update_metadata(study.id, {"category_id": "study"})

    assert [item.id for item in store.list_recent(category_id="meeting")] == [meeting.id]
    assert [item.id for item in store.list_recent(favorite=True)] == [meeting.id]
    assert [item.id for item in store.list_recent(query="动态规划")] == [study.id]
    assert store.list_recent(category_id="uncategorized") == []


def test_store_rejects_missing_category() -> None:
    store = create_store()
    item = create_item("待分类")
    store.add(item)

    with pytest.raises(ValueError, match="分类不存在"):
        store.update_metadata(item.id, {"category_id": "missing"})


def test_store_manages_custom_categories() -> None:
    store = create_store()

    category = store.create_category("产品", "#2563eb")
    updated = store.update_category(category.id, {"name": "产品规划", "color": "#0f766e"})

    assert updated is not None
    assert updated.name == "产品规划"
    assert updated.color == "#0f766e"
    assert store.delete_category(category.id) is True
    assert store.get_category(category.id) is None


def test_store_deleting_category_moves_sessions_to_uncategorized() -> None:
    store = create_store()
    category = store.create_category("临时分类", "#2563eb")
    item = create_item("需要保留的记录")
    store.add(item)
    store.update_metadata(item.id, {"category_id": category.id})

    store.delete_category(category.id)

    updated = store.get(item.id)
    assert updated is not None
    assert updated.category_id is None


def test_store_rejects_deleting_builtin_category() -> None:
    store = create_store()

    with pytest.raises(ValueError, match="内置分类不可删除"):
        store.delete_category("meeting")


def test_store_migrates_legacy_transcript_table() -> None:
    store = create_store()
    connection = store._connect()
    connection.execute("DROP TABLE transcripts")
    connection.execute(
        """
        CREATE TABLE transcripts (
            id TEXT PRIMARY KEY,
            raw_text TEXT NOT NULL,
            processed_text TEXT NOT NULL,
            scene TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    metrics = TranscriptMetrics(
        raw_length=2,
        processed_length=3,
        removed_fillers=0,
        estimated_reading_seconds=1,
    )
    connection.execute(
        """
        INSERT INTO transcripts (
            id, raw_text, processed_text, scene, metrics_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "legacy",
            "旧记录",
            "旧记录。",
            "general",
            metrics.model_dump_json(),
            "2026-05-25T00:00:00+00:00",
        ),
    )

    store._init_schema()
    item = store.get("legacy")

    assert item is not None
    assert item.title == "旧记录。"
    assert item.favorite is False
    assert item.category_id is None
    assert item.updated_at.isoformat() == "2026-05-25T00:00:00+00:00"


def test_store_deletes_item() -> None:
    store = create_store()
    item = create_item("待删除")
    store.add(item)

    assert store.delete(item.id) is True
    assert store.list_recent() == []
    assert store.delete(item.id) is False


def test_store_clears_items() -> None:
    store = create_store()
    store.add(create_item("第一条"))
    store.add(create_item("第二条"))

    store.clear()

    assert store.list_recent() == []


def test_store_reports_health_and_count() -> None:
    store = create_store()
    store.add(create_item("第一条"))

    assert store.ping() is True
    assert store.count() == 1
