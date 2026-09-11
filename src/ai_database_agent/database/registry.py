"""
Milestone 7 — multi-database registry.

Until now the app connected to exactly one database, chosen once at
startup from `DATABASE_URL` in `.env` (see `connection.py`). This
module lets a user add their *own* SQLite database file at runtime
(upload from the chat UI) and keeps a live registry of every database
available in the current process: the original configured one plus
any uploaded ones, each with its own cached SQLAlchemy `Engine`.

Design notes:
  - Uploaded files are copied into `data/uploads/<db_id>.sqlite` so the
    registry never depends on a path outside the project (e.g. a
    browser's temp upload path that may not persist).
  - Only SQLite files are accepted for upload. Validated by literally
    opening the file and running a trivial read-only query before it's
    registered -- rejecting anything that isn't a real SQLite database
    (wrong file type, corrupted upload, zero-byte file, etc.) with a
    clear error instead of a confusing failure three requests later.
- This registry is process-local (an in-memory dict). Milestone 12
  adds disk persistence behind it: every upload is also recorded in
  the StateStore (`storage/state_store.py`), and `reload_from_disk()`
  (called on backend startup) re-registers whatever is still on disk,
  so a restart no longer forgets uploaded databases.
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ai_database_agent.database.connection import (
    create_sqlite_engine,
    get_engine as get_default_engine,
)
from ai_database_agent.observability.logging import get_logger

if TYPE_CHECKING:
    from ai_database_agent.storage.state_store import StateStore

_log = get_logger(__name__)

DEFAULT_DB_ID = "default"


class InvalidDatabaseFileError(ValueError):
    """Raised when an uploaded file is not a valid, readable SQLite database."""


@dataclass
class DatabaseEntry:
    id: str
    name: str
    engine: Engine
    dialect: str
    file_path: str | None = None
    is_default: bool = False


@dataclass
class DatabaseRegistry:
    """Process-wide registry of every database the app can currently query."""

    upload_dir: Path = field(default_factory=lambda: Path("data/uploads"))
    state_store: StateStore | None = None
    _entries: dict[str, DatabaseEntry] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        default_engine = get_default_engine()
        self._entries[DEFAULT_DB_ID] = DatabaseEntry(
            id=DEFAULT_DB_ID,
            name="Default database",
            engine=default_engine,
            dialect=default_engine.dialect.name,
            is_default=True,
        )

    def list_databases(self) -> list[DatabaseEntry]:
        with self._lock:
            return list(self._entries.values())

    def get(self, db_id: str) -> DatabaseEntry:
        with self._lock:
            entry = self._entries.get(db_id)
        if entry is None:
            raise KeyError(f"Unknown database id: {db_id!r}")
        return entry

    def get_engine(self, db_id: str) -> Engine:
        return self.get(db_id).engine

    def add_sqlite_upload(self, source_path: Path, display_name: str) -> DatabaseEntry:
        """Copy an uploaded SQLite file into data/uploads/, validate it
        is actually openable as a database, and register it. Raises
        InvalidDatabaseFileError (not a bare exception) so the API
        layer can turn it into a clean 400 instead of a 500.
        """
        db_id = uuid.uuid4().hex[:12]
        dest_path = self.upload_dir / f"{db_id}.sqlite"

        try:
            shutil.copyfile(source_path, dest_path)
        except OSError as exc:
            _log.exception("registry.upload.copy_failed", extra={"display_name": display_name})
            raise InvalidDatabaseFileError(f"Could not save uploaded file: {exc}") from exc

        engine = create_sqlite_engine(dest_path)
        try:
            with engine.connect() as conn:
                # A real SQLite file has at least this system table;
                # anything else (wrong format, HTML error page saved as
                # .sqlite, empty file) fails here immediately.
                conn.execute(text("SELECT name FROM sqlite_master LIMIT 1"))
        except SQLAlchemyError as exc:
            engine.dispose()
            dest_path.unlink(missing_ok=True)
            _log.warning(
                "registry.upload.invalid_sqlite",
                extra={"display_name": display_name, "error": str(exc)},
            )
            raise InvalidDatabaseFileError(
                "That file doesn't look like a valid SQLite database."
            ) from exc

        entry = DatabaseEntry(
            id=db_id,
            name=display_name,
            engine=engine,
            dialect=engine.dialect.name,
            file_path=str(dest_path),
        )
        if self.state_store is not None:
            try:
                self.state_store.save_database(entry)
            except Exception:
                engine.dispose()
                dest_path.unlink(missing_ok=True)
                _log.exception("registry.upload.state_save_failed", extra={"db_id": db_id})
                raise
        with self._lock:
            self._entries[db_id] = entry
        _log.info(
            "registry.upload.registered",
            extra={"db_id": db_id, "display_name": display_name, "file_path": str(dest_path)},
        )
        return entry

    def reload_from_disk(self) -> int:
        """Re-register uploads recorded in the StateStore whose files
        still exist (Milestone 12). Called once on backend startup so
        previously uploaded databases reappear without re-uploading.
        Stale rows (file gone) are pruned. Returns the reloaded count.
        """
        if self.state_store is None:
            return 0
        reloaded = 0
        for info in self.state_store.list_databases():
            if info.db_id in self._entries:
                continue
            file_path = Path(info.file_path)
            if not file_path.is_file():
                _log.warning("registry.reload.missing_file", extra={"db_id": info.db_id})
                self.state_store.delete_database(info.db_id)
                continue
            try:
                engine = create_sqlite_engine(file_path)
                with engine.connect() as conn:
                    conn.execute(text("SELECT name FROM sqlite_master LIMIT 1"))
            except SQLAlchemyError:
                _log.warning("registry.reload.unreadable", extra={"db_id": info.db_id})
                continue
            with self._lock:
                self._entries[info.db_id] = DatabaseEntry(
                    id=info.db_id,
                    name=info.display_name,
                    engine=engine,
                    dialect=engine.dialect.name,
                    file_path=str(file_path),
                )
            reloaded += 1
        if reloaded:
            _log.info("registry.reload.done", extra={"reloaded": reloaded})
        return reloaded

    def remove(self, db_id: str) -> None:
        if db_id == DEFAULT_DB_ID:
            raise ValueError("Cannot remove the default database.")
        with self._lock:
            entry = self._entries.pop(db_id, None)
        if entry is None:
            return
        entry.engine.dispose()
        if entry.file_path:
            Path(entry.file_path).unlink(missing_ok=True)
        if self.state_store is not None:
            self.state_store.delete_database(db_id)
        _log.info("registry.remove", extra={"db_id": db_id})
