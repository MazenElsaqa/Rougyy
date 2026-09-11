"""
Milestone 5 — conversation memory.

Lets a follow-up question like "what about just from Canada?" or
"and how many of those?" resolve against the *previous* turn instead
of being generated in isolation. Two things carry across turns:

1. Schema linking context -- the combined text of recent turns (not
   just the bare current question) is what gets tokenized for
   schema/table relevance (see schema/linker.py), so a short
   follow-up that shares no words with the current schema still pulls
   in the tables the conversation has actually been about.
2. Generation context -- prior (question, sql) pairs are replayed as
   user/assistant turns before the real question (see
   llm/sql_generator.py's `conversation_turns` parameter), the same
   pattern already used for few-shot exemplars and self-correction
   attempts, so the model sees what was already asked and how it was
   answered in SQL.

`Conversation` is intentionally a thin, bounded window (default: last
5 turns) rather than a full transcript or a summarization step --
those are meaningful upgrades but not needed to prove the reference-
resolution behavior end to end, and an unbounded transcript would
grow the prompt on every turn.

Milestone 12 adds optional disk persistence: `bind_store()` attaches
a `StateStore` (+ session id) so every `add_turn()` is also written
to `data/app_state.sqlite`, and `Conversation.resume()` rebuilds a
session's recent turns from disk after a backend restart instead of
starting blank. Without a bound store the behavior is exactly as
before (pure in-memory window).
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, PrivateAttr

if TYPE_CHECKING:
    from ai_database_agent.storage.state_store import StateStore

DEFAULT_MAX_TURNS = 5


class ConversationTurn(BaseModel):
    """One completed question/SQL/answer exchange."""

    question: str
    sql: str
    answer: str


class Conversation(BaseModel):
    """A bounded, ordered window of recent conversation turns."""

    turns: list[ConversationTurn] = Field(default_factory=list)
    max_turns: int = DEFAULT_MAX_TURNS

    _store: StateStore | None = PrivateAttr(default=None)
    _session_id: str | None = PrivateAttr(default=None)

    def bind_store(self, store: StateStore, session_id: str) -> Conversation:
        """Attach disk persistence: future add_turn() calls also write
        through to the store. Returns self for chaining."""
        self._store = store
        self._session_id = session_id
        return self

    @classmethod
    def resume(cls, session_id: str, store: StateStore | None, max_turns: int = DEFAULT_MAX_TURNS) -> Conversation:
        """Rebuild a session's recent turns from disk (Milestone 12).
        With no store (or nothing saved yet) this is just an empty,
        store-bound conversation."""
        conversation = cls(max_turns=max_turns)
        if store is not None:
            conversation.bind_store(store, session_id)
            rows = store.load_turns(session_id, limit=max_turns)
            # Pair user/assistant rows back into turns by order (robust
            # whether rows were written as pairs or one by one).
            questions = [r.content for r in rows if r.role == "user"]
            answers = [r.content for r in rows if r.role == "assistant"]
            for question, raw in zip(questions, answers):
                try:
                    payload = json.loads(raw)
                    sql, answer = payload.get("sql", ""), payload.get("answer", "")
                except (json.JSONDecodeError, AttributeError):
                    sql, answer = "", raw
                conversation.turns.append(
                    ConversationTurn(question=question, sql=sql, answer=answer)
                )
            conversation.turns = conversation.turns[-max_turns:]
        return conversation

    def add_turn(self, question: str, sql: str, answer: str) -> None:
        self.turns.append(ConversationTurn(question=question, sql=sql, answer=answer))
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]
        if self._store is not None and self._session_id is not None:
            self._store.save_turn_pair(self._session_id, question, sql, answer)

    def recent(self) -> list[ConversationTurn]:
        return list(self.turns)

    def context_text(self) -> str:
        """Combined text of recent turns' questions, for schema-linking purposes."""
        return " ".join(turn.question for turn in self.turns)

    def is_empty(self) -> bool:
        return not self.turns
