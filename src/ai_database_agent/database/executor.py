"""
Phase 3 — Safe Query Executor.

Executes LLM-generated SQL with three layers of protection:

1. Read-only enforcement  — only SELECT statements are allowed.
   Any DDL/DML (INSERT, UPDATE, DELETE, DROP, etc.) is rejected
   before touching the database.

2. Hard timeout          — queries that run longer than
   settings.query_timeout_ms are killed. Protects against
   accidental full-table scans or runaway JOINs.

3. Row cap               — results are capped at MAX_ROWS to prevent
   flooding the LLM context with thousands of rows.

Returns a structured QueryResult (Pydantic) so callers always get
typed data, never raw cursor objects.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Engine, text

from ai_database_agent.config import get_settings
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)

MAX_ROWS = 500
_ALLOWED_KEYWORD = "SELECT"
_BLOCKED_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
    "ALTER", "TRUNCATE", "REPLACE", "ATTACH", "DETACH",
}


class QueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool = False
    execution_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


class QueryExecutor:
    """Executes read-only SQL safely against the configured database."""

    def __init__(self, engine: Engine):
        self._engine = engine
        self._settings = get_settings()

    def execute(self, sql: str) -> QueryResult:
        with _tracer.start_as_current_span("query.execute") as span:
            sql = sql.strip()
            span.set_attribute("query.sql_length", len(sql))

            # --- Layer 1: read-only check (fast, no DB involved) ---
            reject_reason = self._check_read_only(sql)
            if reject_reason:
                span.set_attribute("query.rejected", True)
                return QueryResult(
                    sql=sql, columns=[], rows=[], row_count=0,
                    error=reject_reason,
                )

            # --- Layer 2 & 3: timed execution with row cap ---
            return self._run_with_timeout(sql, span)

    # ------------------------------------------------------------------

    def _check_read_only(self, sql: str) -> str | None:
        first_token = sql.split()[0].upper() if sql.split() else ""
        if first_token != _ALLOWED_KEYWORD:
            return (
                f"Rejected: only SELECT is allowed. "
                f"Statement starts with '{first_token}'."
            )
        for kw in _BLOCKED_KEYWORDS:
            if kw in sql.upper():
                return f"Rejected: SQL contains forbidden keyword '{kw}'."
        return None

    def _run_with_timeout(self, sql: str, span) -> QueryResult:
        timeout_s = self._settings.query_timeout_ms / 1000
        result: QueryResult | None = None
        exc: Exception | None = None

        def _run():
            nonlocal result, exc
            try:
                t0 = time.perf_counter()
                with self._engine.connect() as conn:
                    cursor = conn.execute(text(sql))
                    columns = list(cursor.keys())
                    all_rows = [dict(r._mapping) for r in cursor]
                elapsed_ms = (time.perf_counter() - t0) * 1000

                truncated = len(all_rows) > MAX_ROWS
                rows = all_rows[:MAX_ROWS]

                result = QueryResult(
                    sql=sql,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                    execution_ms=round(elapsed_ms, 2),
                )
            except Exception as e:
                exc = e

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_s)

        if thread.is_alive():
            span.set_attribute("query.timed_out", True)
            return QueryResult(
                sql=sql, columns=[], rows=[], row_count=0,
                error=f"Query timed out after {self._settings.query_timeout_ms}ms.",
            )

        if exc:
            span.set_attribute("query.error", str(exc))
            return QueryResult(
                sql=sql, columns=[], rows=[], row_count=0,
                error=f"Query error: {exc}",
            )

        span.set_attribute("query.row_count", result.row_count)
        span.set_attribute("query.execution_ms", result.execution_ms)
        span.set_attribute("query.truncated", result.truncated)
        return result
