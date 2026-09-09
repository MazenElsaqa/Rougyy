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
"""
from __future__ import annotations

from pydantic import BaseModel, Field

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

    def add_turn(self, question: str, sql: str, answer: str) -> None:
        self.turns.append(ConversationTurn(question=question, sql=sql, answer=answer))
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def recent(self) -> list[ConversationTurn]:
        return list(self.turns)

    def context_text(self) -> str:
        """Combined text of recent turns' questions, for schema-linking purposes."""
        return " ".join(turn.question for turn in self.turns)

    def is_empty(self) -> bool:
        return not self.turns
