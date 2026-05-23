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
        payload = [entry.model_dump(mode="json") for entry in items]
        self.data_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_recent(self) -> list[TranscriptItem]:
        if not self.data_file.exists():
            return []

        try:
            payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        return [TranscriptItem.model_validate(entry) for entry in payload[: self.limit]]
