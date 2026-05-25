import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.app.models import (
    TranscriptCategory,
    TranscriptItem,
    TranscriptMetrics,
    derive_transcript_title,
)

MEMORY_DATABASE = ":memory:"
UNCATEGORIZED_CATEGORY_ID = "uncategorized"

DEFAULT_CATEGORIES = (
    ("meeting", "会议", "#2563eb", 10),
    ("work", "工作", "#0f766e", 20),
    ("study", "学习", "#7c3aed", 30),
    ("idea", "灵感", "#b45309", 40),
    ("code", "代码", "#475569", 50),
)


class TranscriptStore:
    """SQLite-backed transcript session library."""

    def __init__(
        self,
        database_file: str | None = None,
        limit: int = 100,
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
                    id, title, raw_text, processed_text, scene, category_id, favorite,
                    metrics_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.title,
                    item.raw_text,
                    item.processed_text,
                    item.scene,
                    item.category_id,
                    int(item.favorite),
                    item.metrics.model_dump_json(),
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )

    def list_recent(
        self,
        limit: int | None = None,
        category_id: str | None = None,
        favorite: bool | None = None,
        query: str | None = None,
    ) -> list[TranscriptItem]:
        effective_limit = self._normalize_limit(limit)
        where_clauses: list[str] = []
        params: list[object] = []

        if category_id == UNCATEGORIZED_CATEGORY_ID:
            where_clauses.append("category_id IS NULL")
        elif category_id:
            where_clauses.append("category_id = ?")
            params.append(category_id)

        if favorite is not None:
            where_clauses.append("favorite = ?")
            params.append(int(favorite))

        if query:
            like_query = f"%{query.strip()}%"
            where_clauses.append(
                "(title LIKE ? OR raw_text LIKE ? OR processed_text LIKE ?)"
            )
            params.extend([like_query, like_query, like_query])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        params.append(effective_limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id, title, raw_text, processed_text, scene, category_id, favorite,
                    metrics_json, created_at, updated_at
                FROM transcripts
                {where_sql}
                ORDER BY favorite DESC, updated_at DESC, created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._row_to_item(row) for row in rows]

    def list_categories(self) -> list[TranscriptCategory]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, color, sort_order, builtin, created_at, updated_at
                FROM transcript_categories
                ORDER BY sort_order ASC, created_at ASC
                """
            ).fetchall()

        return [self._row_to_category(row) for row in rows]

    def create_category(self, name: str, color: str) -> TranscriptCategory:
        now = datetime.now(UTC).isoformat()
        category_id = str(uuid4())
        sort_order = self._next_category_sort_order()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO transcript_categories (
                        id, name, color, sort_order, builtin, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (category_id, name.strip(), color, sort_order, now, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("分类名称已存在") from exc

        category = self.get_category(category_id)
        if category is None:  # pragma: no cover - defensive guard.
            raise RuntimeError("分类创建失败")
        return category

    def update_category(
        self,
        category_id: str,
        updates: dict[str, object],
    ) -> TranscriptCategory | None:
        if not updates:
            return self.get_category(category_id)

        category = self.get_category(category_id)
        if category is None:
            return None

        fields: list[str] = []
        params: list[object] = []
        if "name" in updates:
            name = str(updates["name"]).strip()
            if not name:
                raise ValueError("分类名称不能为空")
            fields.append("name = ?")
            params.append(name)
        if "color" in updates:
            fields.append("color = ?")
            params.append(str(updates["color"]))

        if not fields:
            return category

        fields.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(category_id)

        try:
            with self._connect() as connection:
                connection.execute(
                    f"UPDATE transcript_categories SET {', '.join(fields)} WHERE id = ?",
                    params,
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("分类名称已存在") from exc

        return self.get_category(category_id)

    def delete_category(self, category_id: str) -> bool:
        with self._connect() as connection:
            category = connection.execute(
                "SELECT builtin FROM transcript_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            if category is None:
                return False
            if bool(category["builtin"]):
                raise ValueError("内置分类不可删除")

            connection.execute(
                "UPDATE transcripts SET category_id = NULL, updated_at = ? WHERE category_id = ?",
                (datetime.now(UTC).isoformat(), category_id),
            )
            cursor = connection.execute(
                "DELETE FROM transcript_categories WHERE id = ?",
                (category_id,),
            )
            return cursor.rowcount > 0

    def get_category(self, category_id: str) -> TranscriptCategory | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, color, sort_order, builtin, created_at, updated_at
                FROM transcript_categories
                WHERE id = ?
                """,
                (category_id,),
            ).fetchone()

        return self._row_to_category(row) if row else None

    def update_metadata(
        self,
        transcript_id: str,
        updates: dict[str, object],
    ) -> TranscriptItem | None:
        if not updates:
            return self.get(transcript_id)

        if "category_id" in updates and updates["category_id"] is not None:
            category_id = str(updates["category_id"])
            if self.get_category(category_id) is None:
                raise ValueError("分类不存在")

        fields: list[str] = []
        params: list[object] = []
        if "title" in updates:
            title = str(updates["title"]).strip()
            if not title:
                raise ValueError("标题不能为空")
            fields.append("title = ?")
            params.append(title)
        if "category_id" in updates:
            fields.append("category_id = ?")
            params.append(updates["category_id"])
        if "favorite" in updates:
            fields.append("favorite = ?")
            params.append(int(bool(updates["favorite"])))

        if not fields:
            return self.get(transcript_id)

        fields.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(transcript_id)

        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE transcripts SET {', '.join(fields)} WHERE id = ?",
                params,
            )
            if cursor.rowcount == 0:
                return None

        return self.get(transcript_id)

    def get(self, transcript_id: str) -> TranscriptItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id, title, raw_text, processed_text, scene, category_id, favorite,
                    metrics_json, created_at, updated_at
                FROM transcripts
                WHERE id = ?
                """,
                (transcript_id,),
            ).fetchone()
        return self._row_to_item(row) if row else None

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
                CREATE TABLE IF NOT EXISTS transcript_categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    builtin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transcripts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    processed_text TEXT NOT NULL,
                    scene TEXT NOT NULL,
                    category_id TEXT REFERENCES transcript_categories(id) ON DELETE SET NULL,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._migrate_transcripts(connection)
            self._seed_categories(connection)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transcripts_created_at
                ON transcripts (created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transcripts_updated_at
                ON transcripts (updated_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transcripts_category_id
                ON transcripts (category_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transcripts_favorite
                ON transcripts (favorite)
                """
            )

    def _migrate_transcripts(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(transcripts)").fetchall()
        }
        if "title" not in columns:
            connection.execute("ALTER TABLE transcripts ADD COLUMN title TEXT")
        if "category_id" not in columns:
            connection.execute("ALTER TABLE transcripts ADD COLUMN category_id TEXT")
        if "favorite" not in columns:
            connection.execute(
                "ALTER TABLE transcripts ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
            )
        if "updated_at" not in columns:
            connection.execute("ALTER TABLE transcripts ADD COLUMN updated_at TEXT")

        rows = connection.execute(
            """
            SELECT id, title, raw_text, processed_text, updated_at, created_at
            FROM transcripts
            WHERE title IS NULL OR title = '' OR updated_at IS NULL OR updated_at = ''
            """
        ).fetchall()
        for row in rows:
            title = row["title"] or derive_transcript_title(
                row["processed_text"] or row["raw_text"]
            )
            updated_at = row["updated_at"] or row["created_at"]
            connection.execute(
                "UPDATE transcripts SET title = ?, updated_at = ? WHERE id = ?",
                (title, updated_at, row["id"]),
            )

    def _seed_categories(self, connection: sqlite3.Connection) -> None:
        now = datetime.now(UTC).isoformat()
        for category_id, name, color, sort_order in DEFAULT_CATEGORIES:
            connection.execute(
                """
                INSERT OR IGNORE INTO transcript_categories (
                    id, name, color, sort_order, builtin, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (category_id, name, color, sort_order, now, now),
            )

    def _next_category_sort_order(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 10 AS next_order FROM transcript_categories"
            ).fetchone()
        return int(row["next_order"])

    def _row_to_item(self, row: sqlite3.Row) -> TranscriptItem:
        return TranscriptItem.model_validate(
            {
                "id": row["id"],
                "title": row["title"],
                "raw_text": row["raw_text"],
                "processed_text": row["processed_text"],
                "scene": row["scene"],
                "category_id": row["category_id"],
                "favorite": bool(row["favorite"]),
                "metrics": TranscriptMetrics.model_validate_json(row["metrics_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    def _row_to_category(self, row: sqlite3.Row) -> TranscriptCategory:
        return TranscriptCategory.model_validate(
            {
                "id": row["id"],
                "name": row["name"],
                "color": row["color"],
                "sort_order": row["sort_order"],
                "builtin": bool(row["builtin"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    def _normalize_limit(self, limit: int | None) -> int:
        if limit is None:
            return self.limit
        return max(1, min(limit, self.limit))
