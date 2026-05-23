import shutil
from pathlib import Path
from uuid import uuid4

from backend.app.models import TranscriptItem, TranscriptMetrics
from backend.app.services.storage import TranscriptStore

TEST_TMP_DIR = Path("backend/data/test-tmp")


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
    TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)
    data_file = TEST_TMP_DIR / f"{uuid4()}.json"
    return TranscriptStore(data_file=str(data_file), limit=limit)


def teardown_module() -> None:
    shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)


def test_store_adds_new_item_first() -> None:
    store = create_store()

    first = create_item("第一条")
    second = create_item("第二条")
    store.add(first)
    store.add(second)

    items = store.list_recent()

    assert [item.id for item in items] == [second.id, first.id]


def test_store_respects_limit() -> None:
    store = create_store(limit=3)

    for index in range(5):
        store.add(create_item(f"第{index}条"))

    assert len(store.list_recent()) == 3
    assert len(store.list_recent(limit=2)) == 2


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
