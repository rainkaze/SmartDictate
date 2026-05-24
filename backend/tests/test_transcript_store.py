import shutil
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from backend.app.models import TranscriptItem, TranscriptMetrics
from backend.app.services.transcript_store import TranscriptStore

TEST_RUNTIME_DIR = Path("backend/data/test-runtime/storage")


@pytest.fixture()
def storage_dir() -> Iterator[Path]:
    test_dir = TEST_RUNTIME_DIR / uuid4().hex
    test_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield test_dir
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


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


def create_store(storage_dir: Path, limit: int = 10) -> TranscriptStore:
    return TranscriptStore(database_file=":memory:", limit=limit)


def test_store_adds_new_item_first(storage_dir: Path) -> None:
    store = create_store(storage_dir)

    first = create_item("第一条")
    second = create_item("第二条")
    store.add(first)
    store.add(second)

    items = store.list_recent()

    assert [item.id for item in items] == [second.id, first.id]


def test_store_respects_limit(storage_dir: Path) -> None:
    store = create_store(storage_dir, limit=3)

    for index in range(5):
        store.add(create_item(f"第{index}条"))

    assert len(store.list_recent()) == 3
    assert len(store.list_recent(limit=2)) == 2


def test_store_deletes_item(storage_dir: Path) -> None:
    store = create_store(storage_dir)
    item = create_item("待删除")
    store.add(item)

    assert store.delete(item.id) is True
    assert store.list_recent() == []
    assert store.delete(item.id) is False


def test_store_clears_items(storage_dir: Path) -> None:
    store = create_store(storage_dir)
    store.add(create_item("第一条"))
    store.add(create_item("第二条"))

    store.clear()

    assert store.list_recent() == []


def test_store_reports_health_and_count(storage_dir: Path) -> None:
    store = create_store(storage_dir)
    store.add(create_item("第一条"))

    assert store.ping() is True
    assert store.count() == 1
