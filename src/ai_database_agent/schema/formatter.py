"""
Phase 2 — Schema Representation.

Converts a DatabaseSchema (from the inspector) into prompt-ready text
formats that the LLM can understand. Two formats are produced:

1. DDL format  — looks like real CREATE TABLE SQL; the LLM already
   knows this syntax from training, so it understands column types,
   primary keys, and foreign-key relationships instantly.

2. Compact format — one-liner per table; used when we need to fit
   the full schema into a tight context window (e.g. RAG retrieval
   stage, or when token budget is low).

Both formats include sample rows so the LLM knows real value shapes
(e.g. that Stadium_ID is stored as TEXT even though it looks like an int).
"""
from __future__ import annotations

from ai_database_agent.database.models import DatabaseSchema, TableSchema
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)


class SchemaFormatter:
    """Converts a DatabaseSchema into LLM-ready text representations."""

    def __init__(self, schema: DatabaseSchema):
        self._schema = schema

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_ddl(self, include_samples: bool = True) -> str:
        """
        Full DDL representation — one CREATE TABLE block per table.
        This is the primary format sent to the LLM for SQL generation.
        """
        with _tracer.start_as_current_span("schema.to_ddl"):
            parts = [f"-- Database dialect: {self._schema.dialect}", ""]
            for table in self._schema.tables:
                parts.append(self._table_to_ddl(table, include_samples))
            return "\n".join(parts).strip()

    def to_compact(self) -> str:
        """
        Compact one-liner per table — used for retrieval / token-budget stages.
        Format: table_name(col1 TYPE, col2 TYPE PK, ...) [FK: col -> other.col]
        """
        with _tracer.start_as_current_span("schema.to_compact"):
            lines = []
            for table in self._schema.tables:
                cols = ", ".join(
                    f"{c.name} {c.type}{'  PK' if c.is_primary_key else ''}"
                    for c in table.columns
                )
                fks = "  ".join(
                    f"FK:{fk.column}->{fk.references_table}.{fk.references_column}"
                    for fk in table.foreign_keys
                )
                line = f"{table.name}({cols})"
                if fks:
                    line += f"  [{fks}]"
                lines.append(line)
            return "\n".join(lines)

    def table_names(self) -> list[str]:
        return [t.name for t in self._schema.tables]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _table_to_ddl(self, table: TableSchema, include_samples: bool) -> str:
        lines = [f"CREATE TABLE {table.name} ("]

        col_lines = []
        for col in table.columns:
            parts = [f"  {col.name}", col.type]
            if col.is_primary_key:
                parts.append("PRIMARY KEY")
            if not col.nullable and not col.is_primary_key:
                parts.append("NOT NULL")
            col_lines.append(" ".join(parts))

        # Foreign key constraints at the bottom of the table definition
        for fk in table.foreign_keys:
            col_lines.append(
                f"  FOREIGN KEY ({fk.column})"
                f" REFERENCES {fk.references_table}({fk.references_column})"
            )

        lines.append(",\n".join(col_lines))
        lines.append(f");  -- {table.row_count} rows")

        if include_samples and table.sample_rows:
            lines.append(f"-- Sample rows from {table.name}:")
            for row in table.sample_rows:
                lines.append(f"--   {dict(row)}")

        lines.append("")
        return "\n".join(lines)
