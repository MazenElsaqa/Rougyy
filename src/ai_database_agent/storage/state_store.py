"""
Persistent app state -- fixes uploaded databases and conversation memory
being lost whenever the backend process restarts.

Both were previously plain in-memory dicts (DatabaseRegistry._entries in
registry.py, backend/main.py's _conversations): correct within a single
run, but a crash, a `--reload` triggered by editing code, or simply
closing the terminal would silently wipe every uploaded database
registration and every conversation's memory -- even though the
uploaded .sqlite files themselves were never deleted from
data/uploads/, they just stopped being registered anywhere.

This module is a tiny SQLite-backed store (a handful of rows, not real
load) so both of those survive a restart:
  - `databases` -- one row per uploaded database, so the registry can
    re-discover and re-register the files already sitting in
    data/uploads/ on the next startup without asking the user to
    upload them again.
  - `conversations` -- one row per session_id, storing the same turns
    already used in memory (Milestone 5), so the last 5 turns survive
    a backend restart (and, with the session_id now persisted in
    localStorage per Milestone 11, a page refresh too) instead of the
    agent "forgetting" what the chat was about.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from ai_database_agent.observability.logging import get_logger

_log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS databases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    dialect TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    session_id TEXT PRIMARY KEY,
    turns_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class StateStore:
    """Thread-safe wrapper around a single SQLite file used for both
    tables above. Opens a fresh connection per call (SQLite handles
    this fine at this scale) instead of holding one long-lived
    connection, so it's safe to share across FastAPI's threadpool with
    just a plain `Lock` around each statement.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        _log.info("state_store.init", extra={"path": str(self.path)})

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- uploaded databases ---------------------------------------------

    def list_uploaded_databases(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, file_path, dialect FROM databases ORDER BY created_at"
            ).fetchall()
        return [{"id": r[0], "name": r[1], "file_path": r[2], "dialect": r[3]} for r in rows]

    def save_uploaded_database(self, db_id: str, name: str, file_path: str, dialect: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO databases (id, name, file_path, dialect) VALUES (?, ?, ?, ?)",
                (db_id, name, file_path, dialect),
            )
        _log.info("state_store.database_saved", extra={"db_id": db_id, "name": name})

    def delete_database(self, db_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM databases WHERE id = ?", (db_id,))
        _log.info("state_store.database_deleted", extra={"db_id": db_id})

    # --- conversation memory ---------------------------------------------

    def load_conversation_turns(self, session_id: str) -> list[dict] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT turns_json FROM conversations WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, ValueError):
            _log.warning("state_store.conversation_corrupt", extra={"session_id": session_id})
            return None

    def save_conversation_turns(self, session_id: str, turns: list[dict]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (session_id, turns_json, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(session_id) DO UPDATE SET
                    turns_json = excluded.turns_json,
                    updated_at = excluded.updated_at
                """,
                (session_id, json.dumps(turns)),
            )

    def delete_conversation(self, session_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        _log.info("state_store.conversation_deleted", extra={"session_id": session_id})
