"""Persistent app-state storage (Milestone 12).

The backend keeps two things in plain process-local dicts: the
multi-database registry (`database/registry.py`) and per-session
conversations (`memory/conversation.py`). Both evaporate on every
restart/reload/crash. This package persists them in a tiny SQLite file
(`data/app_state.sqlite` by default) -- no new infrastructure, same
SQLite the rest of the project already uses.
"""

from ai_database_agent.storage.state_store import DatabaseInfo, StateStore, Turn

__all__ = ["DatabaseInfo", "StateStore", "Turn"]
