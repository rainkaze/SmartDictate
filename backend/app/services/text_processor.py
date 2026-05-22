import re
from dataclasses import dataclass

from backend.app.models import Scene, TranscriptMetrics


@dataclass(frozen=True)
class ProcessedText:
    text: str
    metrics: TranscriptMetrics


class TextProcessor:
    filler_words = ("嗯", "呃", "额", "啊", "那个", "就是", "然后然后")
    hotwords = {
        "七牛": "七牛云",
        "fast api": "FastAPI",
        "法斯特 api": "FastAPI",
        "派森": "Python",
        "威特": "Vite",
        "github": "GitHub",
        "gitee": "Gitee",
        "read me": "README",
    }
    scene_prefixes: dict[Scene, str] = {
        "general": "",
        "meeting": "会议纪要：",
        "study": "学习笔记：",
        "message": "",
        "code_note": "代码说明：",
    }

    def process(self, text: str, scene: Scene = "general") -> ProcessedText:
        normalized = self._normalize_space(text)
        without_fillers, removed_count = self._remove_fillers(normalized)
        corrected = self._apply_hotwords(without_fillers)
        punctuated = self._apply_punctuation(corrected)
        formatted = self._format_by_scene(punctuated, scene)

        metrics = TranscriptMetrics(
            raw_length=len(text),
            processed_length=len(formatted),
            removed_fillers=removed_count,
            estimated_reading_seconds=max(1, round(len(formatted) / 5)),
        )
        return ProcessedText(text=formatted, metrics=metrics)

    def _normalize_space(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _remove_fillers(self, text: str) -> tuple[str, int]:
        removed_count = 0
        cleaned = text
        for word in self.filler_words:
            cleaned, count = re.subn(rf"(?<!\w){re.escape(word)}(?!\w)", "", cleaned)
            removed_count += count
        return self._normalize_space(cleaned), removed_count

    def _apply_hotwords(self, text: str) -> str:
        corrected = text
        for source, target in self.hotwords.items():
            corrected = re.sub(re.escape(source), target, corrected, flags=re.IGNORECASE)
        return corrected

    def _apply_punctuation(self, text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"\s*([，。！？；：,.!?;:])\s*", r"\1", text)
        text = re.sub(r"\s+", "，", text)

        if text[-1] not in "。！？!?":
            text += "。"

        return text

    def _format_by_scene(self, text: str, scene: Scene) -> str:
        prefix = self.scene_prefixes.get(scene, "")
        if not prefix:
            return text
        return f"{prefix}{text}"
