import json
from pathlib import Path

from backend.app.models import HotwordItem
from backend.app.services.text_rules import TextRules, load_text_rules


class HotwordDictionary:
    def __init__(self, data_file: str, base_rules: TextRules | None = None) -> None:
        self.data_file = Path(data_file)
        self.base_rules = base_rules or load_text_rules()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)

    def list_items(self) -> list[HotwordItem]:
        builtin_items = [
            HotwordItem(source=source, target=target, builtin=True)
            for source, target in self.base_rules.hotwords.items()
        ]
        custom_items = [
            HotwordItem(source=source, target=target, builtin=False)
            for source, target in self._read_custom_hotwords().items()
        ]
        return [*builtin_items, *custom_items]

    def add(self, source: str, target: str) -> HotwordItem:
        normalized_source = self._normalize_word(source)
        normalized_target = self._normalize_word(target)
        if not normalized_source or not normalized_target:
            raise ValueError("热词不能为空")

        hotwords = self.get_hotword_map()
        if normalized_source in hotwords:
            raise ValueError("热词已存在")

        custom_hotwords = self._read_custom_hotwords()
        custom_hotwords[normalized_source] = normalized_target
        self._write_custom_hotwords(custom_hotwords)
        return HotwordItem(source=normalized_source, target=normalized_target, builtin=False)

    def delete(self, source: str) -> bool:
        normalized_source = self._normalize_word(source)
        custom_hotwords = self._read_custom_hotwords()
        if normalized_source not in custom_hotwords:
            return False

        del custom_hotwords[normalized_source]
        self._write_custom_hotwords(custom_hotwords)
        return True

    def get_hotword_map(self) -> dict[str, str]:
        return {**self.base_rules.hotwords, **self._read_custom_hotwords()}

    def get_text_rules(self) -> TextRules:
        return TextRules(
            filler_words=self.base_rules.filler_words,
            hotwords=self.get_hotword_map(),
            scene_prefixes=self.base_rules.scene_prefixes,
        )

    def _read_custom_hotwords(self) -> dict[str, str]:
        if not self.data_file.exists():
            return {}

        try:
            payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        return {
            self._normalize_word(source): self._normalize_word(target)
            for source, target in payload.items()
            if self._normalize_word(source) and self._normalize_word(target)
        }

    def _write_custom_hotwords(self, hotwords: dict[str, str]) -> None:
        self.data_file.write_text(
            json.dumps(hotwords, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _normalize_word(self, value: str) -> str:
        return " ".join(value.strip().split())
