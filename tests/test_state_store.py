"""Milestone 12 — SQLite state store: registry + conversation persistence."""

import sqlite3

from ai_database_agent.database.registry import DatabaseRegistry
from ai_database_agent.memory.conversation import Conversation
from ai_database_agent.storage.state_store import StateStore


def _make_sqlite(path):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.execute("INSERT INTO t VALUES ('x')")
    conn.commit()
    conn.close()


def test_save_and_list_databases(tmp_path):
    store = StateStore(tmp_path / "state.sqlite")
    try:
        assert store.list_databases() == []
        store.save_database(
            type("E", (), {"id": "abc", "name": "Mine", "file_path": "/x/y.sqlite", "dialect": "sqlite"})()
        )
        infos = store.list_databases()
        assert len(infos) == 1
        assert infos[0].db_id == "abc"
        assert infos[0].display_name == "Mine"
    finally:
        store.close()


def test_turn_pair_roundtrip_and_limit(tmp_path):
    store = StateStore(tmp_path / "state.sqlite")
    try:
        for i in range(7):
            store.save_turn_pair("s1", f"Q{i}", f"SQL{i}", f"A{i}")
        rows = store.load_turns("s1", limit=5)
        # 5 turns x 2 rows, oldest first, only the last 5 turns kept
        assert len(rows) == 10
        assert rows[0].content == "Q2"
        assert rows[-1].role == "assistant"

        conversation = Conversation.resume("s1", store)
        assert [t.question for t in conversation.turns] == [f"Q{i}" for i in range(2, 7)]
        assert conversation.turns[-1].sql == "SQL6"
        assert conversation.turns[-1].answer == "A6"
    finally:
        store.close()


def test_conversation_bind_writes_through_and_resume_loads(tmp_path):
    store = StateStore(tmp_path / "state.sqlite")
    try:
        conversation = Conversation().bind_store(store, "s9")
        conversation.add_turn("Q1", "SQL1", "A1")
        conversation.add_turn("Q2", "SQL2", "A2")

        resumed = Conversation.resume("s9", store)
        assert [t.question for t in resumed.turns] == ["Q1", "Q2"]
        assert resumed.turns[0].sql == "SQL1"

        store.delete_session_turns("s9")
        assert Conversation.resume("s9", store).is_empty()
    finally:
        store.close()


def test_resume_without_store_is_empty():
    assert Conversation.resume("nope", None).is_empty()


def test_registry_reload_from_disk(tmp_path):
    src = tmp_path / "src.sqlite"
    _make_sqlite(src)
    store = StateStore(tmp_path / "state.sqlite")
    try:
        registry = DatabaseRegistry(upload_dir=tmp_path / "uploads", state_store=store)
        entry = registry.add_sqlite_upload(src, "My DB")
        assert store.list_databases()[0].db_id == entry.id

        # Fresh registry, same on-disk state -> upload reappears without re-uploading.
        fresh = DatabaseRegistry(upload_dir=tmp_path / "uploads", state_store=store)
        assert fresh.reload_from_disk() == 1
        assert [e.id for e in fresh.list_databases() if not e.is_default] == [entry.id]

        # File deleted on disk -> pruned, not resurrected.
        fresh.remove(entry.id)
        assert store.list_databases() == []
        assert fresh.reload_from_disk() == 0
    finally:
        store.close()
