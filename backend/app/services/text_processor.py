import re
from collections.abc import Callable
from dataclasses import dataclass

from backend.app.models import Scene, TranscriptMetrics
from backend.app.services.text_rules import TextRules, load_text_rules


@dataclass(frozen=True)
class ProcessedText:
    text: str
    metrics: TranscriptMetrics


class TextProcessor:
    """负责把语音识别得到的原始文本整理成更适合直接使用的文本。"""

    pause_words = ("然后", "但是", "所以", "因为", "如果", "同时", "另外")

    def __init__(self, rules_provider: Callable[[], TextRules] | None = None) -> None:
        self.rules_provider = rules_provider or load_text_rules

    def process(self, text: str, scene: Scene = "general") -> ProcessedText:
        rules = self.rules_provider()
        normalized = self._normalize_space(text)
        without_fillers, removed_count = self._remove_fillers(normalized, rules)
        corrected = self._apply_hotwords(without_fillers, rules)
        corrected = self._normalize_latin_spacing(corrected)
        punctuated = self._apply_punctuation(corrected)
        formatted = self._format_by_scene(punctuated, scene, rules)

        metrics = TranscriptMetrics(
            raw_length=len(text),
            processed_length=len(formatted),
            removed_fillers=removed_count,
            estimated_reading_seconds=max(1, round(len(formatted) / 5)),
        )
        return ProcessedText(text=formatted, metrics=metrics)

    def _normalize_space(self, text: str) -> str:
        text = text.replace("\u3000", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _remove_fillers(self, text: str, rules: TextRules) -> tuple[str, int]:
        removed_count = 0
        cleaned = text
        for word in rules.filler_words:
            if len(word) == 1:
                cleaned, count = re.subn(
                    rf"(^|[\s，。！？；：,.!?;:]){re.escape(word)}"
                    r"(?=$|[\s，。！？；：,.!?;:]|[\u4e00-\u9fff])",
                    r"\1",
                    cleaned,
                )
            else:
                cleaned, count = re.subn(rf"(?<!\w){re.escape(word)}(?!\w)", "", cleaned)
            removed_count += count
        return self._normalize_space(cleaned), removed_count

    def _apply_hotwords(self, text: str, rules: TextRules) -> str:
        corrected = text
        sorted_hotwords = sorted(
            rules.hotwords.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for source, target in sorted_hotwords:
            corrected = re.sub(re.escape(source), target, corrected, flags=re.IGNORECASE)
        return corrected

    def _normalize_latin_spacing(self, text: str) -> str:
        text = re.sub(r"([\u4e00-\u9fff])([A-Za-z0-9][A-Za-z0-9.+#-]*)", r"\1 \2", text)
        text = re.sub(r"([A-Za-z0-9.+#-]*[A-Za-z0-9])([\u4e00-\u9fff])", r"\1 \2", text)
        return self._normalize_space(text)

    def _apply_punctuation(self, text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"\s*([，。！？；：,.!?;:])\s*", r"\1", text)
        text = self._join_spoken_tokens(text)
        text = self._insert_light_pauses(text)
        text = self._deduplicate_punctuation(text)

        if text[-1] not in "。！？!?":
            text += "。"

        return text

    def _join_spoken_tokens(self, text: str) -> str:
        tokens = [token for token in text.split(" ") if token]
        if not tokens:
            return ""

        result = tokens[0]
        previous = tokens[0]
        for token in tokens[1:]:
            separator = " " if self._should_keep_space(previous, token) else ""
            result = f"{result}{separator}{token}"
            previous = token
        return result

    def _should_keep_space(self, previous: str, current: str) -> bool:
        return self._has_latin_or_digit(previous) or self._has_latin_or_digit(current)

    def _has_latin_or_digit(self, value: str) -> bool:
        return bool(re.search(r"[A-Za-z0-9]", value))

    def _insert_light_pauses(self, text: str) -> str:
        for word in self.pause_words:
            text = re.sub(rf"(?<![，。！？；：]){re.escape(word)}", f"，{word}", text)
        return text.lstrip("，")

    def _deduplicate_punctuation(self, text: str) -> str:
        text = re.sub(r"[，,]{2,}", "，", text)
        text = re.sub(r"[。\.]{2,}", "。", text)
        text = re.sub(r"[！!]{2,}", "！", text)
        text = re.sub(r"[？?]{2,}", "？", text)
        return text

    def _format_by_scene(self, text: str, scene: Scene, rules: TextRules) -> str:
        prefix = rules.scene_prefixes.get(scene, "")
        if not prefix:
            return text
        return f"{prefix}{text}"
