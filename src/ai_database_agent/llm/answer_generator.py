"""
Milestone 1 — Answer generation.

Formats the already-executed query's rows and asks the LLM to phrase
a grounded natural-language answer. The LLM never sees the database
connection here — only the capped, already-executed QueryResult — so
it cannot hallucinate rows that weren't actually returned.
"""
from __future__ import annotations

import json

from ai_database_agent.config import get_settings
from ai_database_agent.database.executor import QueryResult
from ai_database_agent.llm.client import get_llm_client, llm_answer_model_name
from ai_database_agent.llm.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    UNANSWERABLE_SYSTEM_PROMPT,
)
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)

MAX_ROWS_IN_PROMPT = 50


class AnswerGenerator:
    """Turns a question + SQL + QueryResult into a grounded natural-language answer."""

    def __init__(self, client=None, model: str | None = None):
        self._client = client or get_llm_client()
        self._model = model or llm_answer_model_name()

    def generate(self, question: str, sql: str, query_result: QueryResult) -> str:
        with _tracer.start_as_current_span("llm.generate_answer") as span:
            span.set_attribute("llm.model", self._model)

            rows_preview = query_result.rows[:MAX_ROWS_IN_PROMPT]
            rows_json = json.dumps(rows_preview, default=str)

            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=[
                    {"role": "system", "content": ANSWER_GENERATION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question}\n"
                            f"SQL executed: {sql}\n"
                            f"Row count: {query_result.row_count}\n"
                            f"Rows (JSON): {rows_json}"
                        ),
                    },
                ],
            )
            return (response.choices[0].message.content or "").strip()

    def generate_chat_reply(
        self,
        question: str,
        table_names: list[str] | None = None,
        conversation_turns: list | None = None,
    ) -> str:
        """Short conversational reply for CHAT intent: no schema, no
        SQL, just the small chat model with a little history."""
        with _tracer.start_as_current_span("llm.generate_chat_reply") as span:
            span.set_attribute("llm.model", self._model)
            tables = ", ".join(table_names or []) or "the connected database"
            messages: list[dict[str, str]] = [
                {"role": "system", "content": CHAT_SYSTEM_PROMPT.format(tables=tables or "the database")},
            ]
            for turn in (conversation_turns or [])[-3:]:
                messages.append({"role": "user", "content": turn.question})
                messages.append({"role": "assistant", "content": turn.answer})
            messages.append({"role": "user", "content": question})
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=messages,
            )
            return (response.choices[0].message.content or "").strip()

    def generate_unanswerable_reply(self, question: str, table_names: list[str] | None = None) -> str:
        """Friendly explanation when a DATA_QUERY can't be answered
        from the available tables (sentinel SQL / zero linked tables)."""
        with _tracer.start_as_current_span("llm.generate_unanswerable_reply") as span:
            span.set_attribute("llm.model", self._model)
            tables = ", ".join(table_names or [])
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": UNANSWERABLE_SYSTEM_PROMPT.format(tables=tables or "the database"),
                    },
                    {"role": "user", "content": question},
                ],
            )
            return (response.choices[0].message.content or "").strip()
