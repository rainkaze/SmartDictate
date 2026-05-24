import os
import sqlite3
from pathlib import Path

from backend.app.models import TranscriptItem, TranscriptMetrics

MEMORY_DATABASE = ":memory:"


class TranscriptStore:
    """使用 SQLite 持久化保存转写历史。

    SQLite 不需要额外服务进程，适合本项目的本地优先定位；同时它比 JSON 文件更接近真实项目的
    数据访问方式，便于后续迁移到 MySQL、PostgreSQL 等数据库。
    """

    def __init__(
        self,
        database_file: str | None = None,
        limit: int = 30,
        data_file: str | None = None,
    ) -> None:
        default_path = Path("backend/data/smartdictate.sqlite3")
        raw_path = (
            database_file
            or data_file
            or os.getenv("SMART_DICTATE_DATABASE_FILE", default_path)
        )
        self.database_file = str(raw_path)
        self.limit = limit
        self._memory_connection: sqlite3.Connection | None = None
        if self.database_file == MEMORY_DATABASE:
            self._memory_connection = self._create_connection(self.database_file)
        else:
            Path(self.database_file).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def add(self, item: TranscriptItem) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO transcripts (
                    id, raw_text, processed_text, scene, metrics_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.raw_text,
                    item.processed_text,
                    item.scene,
                    item.metrics.model_dump_json(),
                    item.created_at.isoformat(),
                ),
            )
            self._trim_old_items(connection)

    def list_recent(self, limit: int | None = None) -> list[TranscriptItem]:
        effective_limit = self._normalize_limit(limit)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, raw_text, processed_text, scene, metrics_json, created_at
                FROM transcripts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (effective_limit,),
            ).fetchall()

        return [self._row_to_item(row) for row in rows]

    def delete(self, transcript_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM transcripts WHERE id = ?",
                (transcript_id,),
            )
            return cursor.rowcount > 0

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM transcripts")

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM transcripts").fetchone()
        return int(row["total"])

    def ping(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            return False
        return True

    def _connect(self) -> sqlite3.Connection:
        if self._memory_connection is not None:
            return self._memory_connection
        return self._create_connection(self.database_file)

    def _create_connection(self, database_file: str) -> sqlite3.Connection:
        connection = sqlite3.connect(database_file)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transcripts (
                    id TEXT PRIMARY KEY,
                    raw_text TEXT NOT NULL,
                    processed_text TEXT NOT NULL,
                    scene TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transcripts_created_at
                ON transcripts (created_at DESC)
                """
            )

    def _trim_old_items(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            DELETE FROM transcripts
            WHERE id NOT IN (
                SELECT id
                FROM transcripts
                ORDER BY created_at DESC
                LIMIT ?
            )
            """,
            (self.limit,),
        )

    def _row_to_item(self, row: sqlite3.Row) -> TranscriptItem:
        return TranscriptItem.model_validate(
            {
                "id": row["id"],
                "raw_text": row["raw_text"],
                "processed_text": row["processed_text"],
                "scene": row["scene"],
                "metrics": TranscriptMetrics.model_validate_json(row["metrics_json"]),
                "created_at": row["created_at"],
            }
        )

    def _normalize_limit(self, limit: int | None) -> int:
        if limit is None:
            return self.limit
        return max(1, min(limit, self.limit))
