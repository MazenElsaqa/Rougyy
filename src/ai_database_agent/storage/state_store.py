"""
Milestone 12 — SQLite state store.

Persists the two things the backend otherwise keeps only in RAM:

1. `databases` -- every user-uploaded database (id, display name,
   file path, dialect), so a restart can re-register them from
   `data/uploads/` without re-uploading.
2. `conversation_turns` -- per-session (question, sql, answer) turns,
   stored as (turn_index, role, content) rows, so a resumed session
   picks up its last turns instead of starting blank.

Threading: a single `threading.Lock` guards all access and sqlite
runs in WAL mode, so the `--reload` worker and concurrent requests
don't corrupt the file. One connection is kept open per StateStore;
call `.close()` when done (tests) -- the backend keeps one for the
process lifetime.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DatabaseInfo:
    db_id: str
    display_name: str
    file_path: str
    dialect: str
    created_at: str


@dataclass
class Turn:
    turn_index: int
    role: str  # 'user' or 'assistant'
    content: str
    created_at: str


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """Tiny SQLite-backed persistence for registry + conversation state."""

    def __init__(self, path: Path | str = "data/app_state.sqlite"):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS databases (
                    db_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    dialect TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS conversation_turns (
                    session_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_index, role)
                )"""
            )
            self._conn.commit()

    # --- databases --------------------------------------------------------

    def save_database(self, db_info) -> None:
        """Upsert one registry entry. `db_info` is the registry's
        DatabaseEntry (duck-typed: id/name/file_path/dialect) so this
        module doesn't import the registry and create a cycle."""
        if not db_info.file_path:
            return
        with self._lock:
            self._conn.execute(
                """INSERT INTO databases (db_id, display_name, file_path, dialect, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(db_id) DO UPDATE SET
                     display_name=excluded.display_name,
                     file_path=excluded.file_path,
                     dialect=excluded.dialect""",
                (db_info.id, db_info.name, db_info.file_path, db_info.dialect, _utcnow()),
            )
            self._conn.commit()

    def list_databases(self) -> list[DatabaseInfo]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT db_id, display_name, file_path, dialect, created_at"
                " FROM databases ORDER BY created_at"
            ).fetchall()
        return [DatabaseInfo(**dict(r)) for r in rows]

    def delete_database(self, db_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM databases WHERE db_id = ?", (db_id,))
            self._conn.commit()

    # --- conversation turns -----------------------------------------------

    def save_turn(self, session_id: str, role: str, content: str) -> None:
        """Append one (role, content) row. The turn_index is assigned
        from the session's current max so concurrent writers can't
        reuse an index (one lock, one transaction)."""
        if role not in ("user", "assistant"):
            raise ValueError(f"role must be 'user' or 'assistant', got {role!r}")
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(turn_index), -1) FROM conversation_turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            turn_index = int(row[0]) + 1
            self._conn.execute(
                """INSERT INTO conversation_turns
                   (session_id, turn_index, role, content, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, turn_index, role, content, _utcnow()),
            )
            self._conn.commit()

    def save_turn_pair(self, session_id: str, question: str, sql: str, answer: str) -> None:
        """Persist one completed Q/SQL/answer turn as a user row plus an
        assistant row (JSON-packed sql+answer) sharing one turn_index,
        atomically."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(turn_index), -1) FROM conversation_turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            turn_index = int(row[0]) + 1
            now = _utcnow()
            self._conn.execute(
                """INSERT INTO conversation_turns
                   (session_id, turn_index, role, content, created_at)
                   VALUES (?, ?, 'user', ?, ?)""",
                (session_id, turn_index, question, now),
            )
            self._conn.execute(
                """INSERT INTO conversation_turns
                   (session_id, turn_index, role, content, created_at)
                   VALUES (?, ?, 'assistant', ?, ?)""",
                (session_id, turn_index, json.dumps({"sql": sql, "answer": answer}), now),
            )
            self._conn.commit()

    def load_turns(self, session_id: str, limit: int = 5) -> list[Turn]:
        """Raw (role, content) rows for a session, oldest first, capped
        to the last `limit` turns (a turn = one user+assistant pair)."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT turn_index, role, content, created_at FROM conversation_turns
                   WHERE session_id = ?
                     AND turn_index >= (
                       SELECT COALESCE(MAX(turn_index), 0) - ? + 1
                       FROM conversation_turns WHERE session_id = ?
                     )
                   ORDER BY turn_index, CASE role WHEN 'user' THEN 0 ELSE 1 END""",
                (session_id, limit, session_id),
            ).fetchall()
        return [Turn(**dict(r)) for r in rows]

    def delete_session_turns(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM conversation_turns WHERE session_id = ?", (session_id,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
