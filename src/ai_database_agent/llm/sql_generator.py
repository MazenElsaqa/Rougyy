"""
Milestone 1 — SQL generation. Extended in Milestone 3 for self-correction.

Sends the question + schema DDL to an OpenAI-compatible LLM and
extracts a single SQL statement from the response. This is the
"generate" half of the walking skeleton; the result is never
trusted directly — it always passes through database/validator.py
and then the read-only executor before touching real data.

Milestone 3 adds an optional `attempts` history: prior (sql, error)
pairs for the same question are replayed into the conversation as
assistant/user turns so the LLM sees exactly what it tried and why
it failed, then is asked to correct it — the standard self-correction
pattern for text-to-SQL.

Milestone 4 adds an optional `exemplars` list: a handful of curated
(question, SQL) pairs replayed as user/assistant turns *before* the
real question, so the model sees the expected output style through
worked examples rather than instructions alone.

Milestone 5 adds an optional `conversation_turns` list: prior
(question, sql) pairs from the *same conversation* (not curated
exemplars) replayed the same way, immediately before the real
question, so a follow-up like "what about just from Canada?" or
"and how many of those?" can be resolved against what was actually
already asked and answered rather than starting from a blank slate.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from ai_database_agent.config import get_settings
from ai_database_agent.llm.client import get_llm_client, llm_model_name
from ai_database_agent.llm.exemplars import SQLExemplar
from ai_database_agent.llm.prompts import CORRECTION_USER_TEMPLATE, SQL_GENERATION_SYSTEM_PROMPT
from ai_database_agent.memory.conversation import ConversationTurn
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)

_CODE_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_SQL_LABEL_RE = re.compile(r"^\s*sql\s*:?\s*", re.IGNORECASE)


class CorrectionAttempt(BaseModel):
    """One prior (rejected or failed) SQL attempt, fed back to the LLM to correct."""

    sql: str
    error: str


class SQLGenerator:
    """Generates a single SQL SELECT statement for a natural-language question."""

    def __init__(self, client=None, model: str | None = None):
        self._client = client or get_llm_client()
        self._model = model or llm_model_name()

    def generate(
        self,
        question: str,
        schema_ddl: str,
        attempts: list[CorrectionAttempt] | None = None,
        exemplars: list[SQLExemplar] | None = None,
        conversation_turns: list[ConversationTurn] | None = None,
    ) -> str:
        with _tracer.start_as_current_span("llm.generate_sql") as span:
            span.set_attribute("llm.model", self._model)
            span.set_attribute("llm.prior_attempts", len(attempts or []))
            span.set_attribute("llm.exemplar_count", len(exemplars or []))
            span.set_attribute("llm.conversation_turn_count", len(conversation_turns or []))

            messages: list[dict[str, str]] = [
                {"role": "system", "content": SQL_GENERATION_SYSTEM_PROMPT},
            ]
            for exemplar in exemplars or []:
                messages.append({"role": "user", "content": f"Question: {exemplar.question}\n\nSQL:"})
                messages.append({"role": "assistant", "content": exemplar.sql})

            for turn in conversation_turns or []:
                messages.append({"role": "user", "content": f"Question: {turn.question}\n\nSQL:"})
                messages.append({"role": "assistant", "content": turn.sql})

            messages.append(
                {
                    "role": "user",
                    "content": f"Schema:\n{schema_ddl}\n\nQuestion: {question}\n\nSQL:",
                }
            )
            for attempt in attempts or []:
                messages.append({"role": "assistant", "content": attempt.sql})
                messages.append(
                    {
                        "role": "user",
                        "content": CORRECTION_USER_TEMPLATE.format(error=attempt.error),
                    }
                )

            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=messages,
            )
            raw = response.choices[0].message.content or ""
            sql = self._extract_sql(raw)
            span.set_attribute("llm.sql_length", len(sql))
            return sql

    @staticmethod
    def _extract_sql(raw: str) -> str:
        text = raw.strip()

        fence_match = _CODE_FENCE_RE.search(text)
        if fence_match:
            text = fence_match.group(1).strip()

        text = _SQL_LABEL_RE.sub("", text).strip()
        return text.rstrip(";").strip()
