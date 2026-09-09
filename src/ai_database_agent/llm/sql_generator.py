"""
Milestone 1 — SQL generation.

Sends the question + schema DDL to an OpenAI-compatible LLM and
extracts a single SQL statement from the response. This is the
"generate" half of the walking skeleton; the result is never
trusted directly — it always passes through database/validator.py
and then the read-only executor before touching real data.
"""
from __future__ import annotations

import re

from ai_database_agent.config import get_settings
from ai_database_agent.llm.client import get_llm_client
from ai_database_agent.llm.prompts import SQL_GENERATION_SYSTEM_PROMPT
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)

_CODE_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_SQL_LABEL_RE = re.compile(r"^\s*sql\s*:?\s*", re.IGNORECASE)


class SQLGenerator:
    """Generates a single SQL SELECT statement for a natural-language question."""

    def __init__(self, client=None, model: str | None = None):
        self._client = client or get_llm_client()
        self._model = model or get_settings().llm_model

    def generate(self, question: str, schema_ddl: str) -> str:
        with _tracer.start_as_current_span("llm.generate_sql") as span:
            span.set_attribute("llm.model", self._model)

            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SQL_GENERATION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Schema:\n{schema_ddl}\n\nQuestion: {question}\n\nSQL:",
                    },
                ],
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
