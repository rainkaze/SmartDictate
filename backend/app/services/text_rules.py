import json
from dataclasses import dataclass
from pathlib import Path

from backend.app.models import Scene


@dataclass(frozen=True)
class TextRules:
    filler_words: tuple[str, ...]
    hotwords: dict[str, str]
    scene_prefixes: dict[Scene, str]


def load_text_rules(rule_file: Path | None = None) -> TextRules:
    path = rule_file or Path(__file__).resolve().parents[1] / "config" / "text_rules.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    return TextRules(
        filler_words=tuple(payload["filler_words"]),
        hotwords=dict(payload["hotwords"]),
        scene_prefixes=dict(payload["scene_prefixes"]),
    )
