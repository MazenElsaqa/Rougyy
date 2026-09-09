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
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from ai_database_agent.config import get_settings
from ai_database_agent.llm.client import get_llm_client
from ai_database_agent.llm.prompts import CORRECTION_USER_TEMPLATE, SQL_GENERATION_SYSTEM_PROMPT
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
        self._model = model or get_settings().llm_model

    def generate(
        self,
        question: str,
        schema_ddl: str,
        attempts: list[CorrectionAttempt] | None = None,
    ) -> str:
        with _tracer.start_as_current_span("llm.generate_sql") as span:
            span.set_attribute("llm.model", self._model)
            span.set_attribute("llm.prior_attempts", len(attempts or []))

            messages: list[dict[str, str]] = [
                {"role": "system", "content": SQL_GENERATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Schema:\n{schema_ddl}\n\nQuestion: {question}\n\nSQL:",
                },
            ]
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
