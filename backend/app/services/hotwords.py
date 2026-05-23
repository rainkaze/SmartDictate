import os
import sqlite3
from pathlib import Path

from backend.app.models import HotwordItem
from backend.app.services.text_rules import TextRules, load_text_rules

MEMORY_DATABASE = ":memory:"


class HotwordDictionary:
    """管理内置热词和用户自定义热词。

    内置热词继续来自代码仓库中的配置文件，保证作品开箱可用；用户自定义热词写入 SQLite，保证
    多次启动后仍然保留，同时避免把个人数据提交到 Git 仓库。
    """

    def __init__(
        self,
        database_file: str | None = None,
        base_rules: TextRules | None = None,
        data_file: str | None = None,
    ) -> None:
        default_path = Path("backend/data/smartdictate.sqlite3")
        raw_path = (
            database_file
            or data_file
            or os.getenv("SMART_DICTATE_DATABASE_FILE", default_path)
        )
        self.database_file = str(raw_path)
        self._memory_connection: sqlite3.Connection | None = None
        if self.database_file == MEMORY_DATABASE:
            self._memory_connection = self._create_connection(self.database_file)
        else:
            Path(self.database_file).parent.mkdir(parents=True, exist_ok=True)
        self.base_rules = base_rules or load_text_rules()
        self._init_schema()

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

        if normalized_source in self.get_hotword_map():
            raise ValueError("热词已存在")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO hotwords (source, target)
                VALUES (?, ?)
                """,
                (normalized_source, normalized_target),
            )
        return HotwordItem(source=normalized_source, target=normalized_target, builtin=False)

    def delete(self, source: str) -> bool:
        normalized_source = self._normalize_word(source)
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM hotwords WHERE source = ?",
                (normalized_source,),
            )
            return cursor.rowcount > 0

    def get_hotword_map(self) -> dict[str, str]:
        return {**self.base_rules.hotwords, **self._read_custom_hotwords()}

    def get_text_rules(self) -> TextRules:
        return TextRules(
            filler_words=self.base_rules.filler_words,
            hotwords=self.get_hotword_map(),
            scene_prefixes=self.base_rules.scene_prefixes,
        )

    def count_custom(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM hotwords").fetchone()
        return int(row["total"])

    def ping(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            return False
        return True

    def _read_custom_hotwords(self) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source, target
                FROM hotwords
                ORDER BY created_at ASC, source ASC
                """
            ).fetchall()

        return {row["source"]: row["target"] for row in rows}

    def _connect(self) -> sqlite3.Connection:
        if self._memory_connection is not None:
            return self._memory_connection
        return self._create_connection(self.database_file)

    def _create_connection(self, database_file: str) -> sqlite3.Connection:
        connection = sqlite3.connect(database_file)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS hotwords (
                    source TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _normalize_word(self, value: str) -> str:
        return " ".join(value.strip().split())
