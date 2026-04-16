from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import ChatTurn


class SQLiteChatHistoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_channel_id
                ON chat_messages (session_id, channel, id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assistant_message_id INTEGER,
                    session_id TEXT,
                    channel TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    note TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_feedback_message_id
                ON chat_feedback (assistant_message_id, created_at)
                """
            )

    def add_message(
        self,
        *,
        session_id: str,
        channel: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        params = (
            session_id,
            channel,
            role,
            content.strip(),
            json.dumps(metadata or {}, ensure_ascii=False),
            created_at,
        )
        query = (
            "INSERT INTO chat_messages "
            "(session_id, channel, role, content, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )

        if connection is not None:
            cursor = connection.execute(query, params)
            return int(cursor.lastrowid)

        with self._connect() as local_connection:
            cursor = local_connection.execute(query, params)
            return int(cursor.lastrowid)

    def add_exchange(
        self,
        *,
        session_id: str,
        channel: str,
        user_message: str,
        assistant_message: str,
        user_metadata: dict[str, Any] | None = None,
        assistant_metadata: dict[str, Any] | None = None,
    ) -> dict[str, int]:
        with self._connect() as connection:
            user_message_id = self.add_message(
                session_id=session_id,
                channel=channel,
                role="user",
                content=user_message,
                metadata=user_metadata,
                connection=connection,
            )
            assistant_message_id = self.add_message(
                session_id=session_id,
                channel=channel,
                role="assistant",
                content=assistant_message,
                metadata=assistant_metadata,
                connection=connection,
            )
        return {
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        }

    def get_recent_history(
        self,
        *,
        session_id: str,
        channel: str,
        limit_messages: int,
    ) -> list[ChatTurn]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE session_id = ? AND channel = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, channel, limit_messages),
            ).fetchall()

        rows = list(reversed(rows))
        return [
            ChatTurn(role=row["role"], content=row["content"])
            for row in rows
            if row["role"] in {"user", "assistant"} and str(row["content"]).strip()
        ]

    def list_messages(
        self,
        *,
        session_id: str,
        channel: str,
        limit_messages: int,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, session_id, channel, role, content, metadata_json, created_at
                FROM chat_messages
                WHERE session_id = ? AND channel = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, channel, limit_messages),
            ).fetchall()

        messages: list[dict[str, Any]] = []
        for row in reversed(rows):
            metadata_raw = row["metadata_json"] or "{}"
            try:
                metadata = json.loads(metadata_raw)
            except json.JSONDecodeError:
                metadata = {}
            messages.append(
                {
                    "id": int(row["id"]),
                    "session_id": str(row["session_id"]),
                    "channel": str(row["channel"]),
                    "role": str(row["role"]),
                    "content": str(row["content"]),
                    "created_at": str(row["created_at"]),
                    "metadata": metadata,
                }
            )
        return messages

    def count_messages(self, *, session_id: str, channel: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM chat_messages
                WHERE session_id = ? AND channel = ?
                """,
                (session_id, channel),
            ).fetchone()
        return int(row["total"] if row is not None else 0)

    def clear_session(self, *, session_id: str, channel: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM chat_messages
                WHERE session_id = ? AND channel = ?
                """,
                (session_id, channel),
            )
            return int(cursor.rowcount)

    def add_feedback(
        self,
        *,
        assistant_message_id: int | None,
        session_id: str | None,
        channel: str,
        rating: str,
        note: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_feedback
                (assistant_message_id, session_id, channel, rating, note, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assistant_message_id,
                    session_id,
                    channel,
                    rating,
                    (note or "").strip() or None,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    created_at,
                ),
            )
            return int(cursor.lastrowid)
