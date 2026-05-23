import json
import os
from pathlib import Path

from backend.app.models import TranscriptItem


class TranscriptStore:
    def __init__(self, data_file: str | None = None, limit: int = 30) -> None:
        default_path = Path("backend/data/transcripts.json")
        self.data_file = Path(data_file or os.getenv("SMART_DICTATE_DATA_FILE", default_path))
        self.limit = limit
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

    def add(self, item: TranscriptItem) -> None:
        items = [item, *self.list_recent()]
        items = items[: self.limit]
        self._write_items(items)

    def list_recent(self, limit: int | None = None) -> list[TranscriptItem]:
        effective_limit = self._normalize_limit(limit)
        return self._read_items()[:effective_limit]

    def delete(self, transcript_id: str) -> bool:
        items = self._read_items()
        kept_items = [item for item in items if item.id != transcript_id]
        if len(kept_items) == len(items):
            return False
        self._write_items(kept_items)
        return True

    def clear(self) -> None:
        self._write_items([])

    def _read_items(self) -> list[TranscriptItem]:
        if not self.data_file.exists():
            return []

        try:
            payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        return [TranscriptItem.model_validate(entry) for entry in payload]

    def _write_items(self, items: list[TranscriptItem]) -> None:
        payload = [entry.model_dump(mode="json") for entry in items]
        self.data_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _normalize_limit(self, limit: int | None) -> int:
        if limit is None:
            return self.limit
        return max(1, min(limit, self.limit))
