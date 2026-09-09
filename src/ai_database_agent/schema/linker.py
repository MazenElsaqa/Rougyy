"""
Milestone 4 — lightweight schema linking.

Identifies which tables (and columns) are actually relevant to a
question before generation, using keyword/token overlap between the
question and schema names -- no embeddings, no vector store. This is
deliberately not vector-based RAG: for schemas with a handful of
tables (concert_singer has 4), keyword overlap over table/column
names is both cheap and accurate, and the failure mode of a vector
search miss isn't worth the added latency and infrastructure until
the schema is much larger. Graduate to embeddings-based retrieval
only once schema size actually demands it (see MILESTONES.md).

Two things happen here:

1. Table relevance scoring + FK closure -- token overlap between the
   question and each table's name/columns selects a candidate set,
   which is then expanded to include any table connected to a
   candidate by a foreign key (in either direction) so joins the
   question needs aren't dropped just because the join table's own
   name has no lexical overlap with the question (e.g. a question
   about "singers" and "concerts" still pulls in the join table
   `singer_in_concert`, which shares no token with either word).

2. Value grounding -- for small categorical TEXT columns, expose the
   real distinct values so the LLM can match the question's wording
   to the value as actually stored (e.g. "USA" vs "United States")
   instead of guessing a plausible-looking string.
"""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import Engine, text

from ai_database_agent.database.models import DatabaseSchema, TableSchema
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "for", "is", "are", "was", "were",
    "what", "which", "who", "how", "many", "much", "list", "show", "find",
    "and", "or", "to", "with", "by", "that", "this", "does", "do", "did",
    "each", "all", "name", "names", "id",
}

DEFAULT_MAX_DISTINCT_VALUES = 8
DEFAULT_MAX_VALUE_LENGTH = 40


def _tokenize(value: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(value.lower()) if t not in _STOPWORDS and len(t) > 2}


class SchemaLinker:
    """Scores and filters a DatabaseSchema down to the tables relevant to a question."""

    def __init__(self, engine: Engine | None = None, max_distinct_values: int = DEFAULT_MAX_DISTINCT_VALUES):
        self._engine = engine
        self._max_distinct_values = max_distinct_values

    def link(self, question: str, schema: DatabaseSchema, min_tables: int = 2) -> DatabaseSchema:
        """
        Returns a DatabaseSchema containing only tables relevant to
        `question`, expanded via foreign-key closure so joins aren't
        lost. Falls back to the full schema if fewer than `min_tables`
        tables score above zero -- a question with no lexical overlap
        at all is safer answered with full context than a narrow,
        possibly-wrong guess.
        """
        with _tracer.start_as_current_span("schema.link") as span:
            span.set_attribute("schema.link.table_count", len(schema.tables))
            question_tokens = _tokenize(question)
            scores = {t.name: self._score_table(question_tokens, t) for t in schema.tables}
            relevant = {name for name, score in scores.items() if score > 0}

            if len(relevant) < min_tables:
                span.set_attribute("schema.link.fallback_full_schema", True)
                return schema

            relevant = self._fk_closure(relevant, schema)
            span.set_attribute("schema.link.selected_tables", ",".join(sorted(relevant)))

            linked_tables = [t for t in schema.tables if t.name in relevant]
            return DatabaseSchema(dialect=schema.dialect, tables=linked_tables)

    def value_hints(self, schema: DatabaseSchema) -> dict[str, dict[str, list[str]]]:
        """
        For each small categorical TEXT column in `schema`, returns up
        to `max_distinct_values` real distinct values so the LLM can
        match the question's wording to the value as actually stored.
        Returns {} if no engine was provided. Columns with more than
        `max_distinct_values` distinct values, or values longer than
        `DEFAULT_MAX_VALUE_LENGTH` chars, are skipped as likely free
        text rather than a categorical filter column.
        """
        if self._engine is None:
            return {}

        with _tracer.start_as_current_span("schema.value_hints") as span:
            hints: dict[str, dict[str, list[str]]] = {}
            for table in schema.tables:
                table_hints = self._table_value_hints(table)
                if table_hints:
                    hints[table.name] = table_hints
            span.set_attribute("schema.value_hints.table_count", len(hints))
            return hints

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_table(question_tokens: set[str], table: TableSchema) -> int:
        table_tokens = _tokenize(table.name)
        column_tokens: Counter[str] = Counter()
        for col in table.columns:
            column_tokens.update(_tokenize(col.name))

        score = 2 * len(question_tokens & table_tokens)
        score += len(question_tokens & set(column_tokens))
        return score

    @staticmethod
    def _fk_closure(selected: set[str], schema: DatabaseSchema) -> set[str]:
        """Expand `selected` to every table reachable by a foreign key, either direction."""
        closure = set(selected)
        by_name = {t.name: t for t in schema.tables}
        changed = True
        while changed:
            changed = False
            for name in list(closure):
                table = by_name.get(name)
                if table is None:
                    continue
                for fk in table.foreign_keys:
                    if fk.references_table not in closure:
                        closure.add(fk.references_table)
                        changed = True
            for table in schema.tables:
                if table.name in closure:
                    continue
                if any(fk.references_table in closure for fk in table.foreign_keys):
                    closure.add(table.name)
                    changed = True
        return closure

    def _table_value_hints(self, table: TableSchema) -> dict[str, list[str]]:
        text_columns = [c for c in table.columns if self._is_text_like(c.type)]
        if not text_columns:
            return {}

        hints: dict[str, list[str]] = {}
        with self._engine.connect() as conn:
            for col in text_columns:
                try:
                    result = conn.execute(
                        text(
                            f'SELECT DISTINCT "{col.name}" FROM "{table.name}" '
                            f'WHERE "{col.name}" IS NOT NULL LIMIT :limit'
                        ),
                        {"limit": self._max_distinct_values + 1},
                    )
                    values = [str(row[0]) for row in result]
                except Exception:
                    continue

                if not values or len(values) > self._max_distinct_values:
                    continue  # likely free text, not a small categorical set
                if any(len(v) > DEFAULT_MAX_VALUE_LENGTH for v in values):
                    continue
                hints[col.name] = values
        return hints

    @staticmethod
    def _is_text_like(sql_type: str) -> bool:
        upper = sql_type.upper()
        return "CHAR" in upper or "TEXT" in upper or "CLOB" in upper
