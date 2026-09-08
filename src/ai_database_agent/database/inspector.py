"""
Database Inspector (Phase 1, section 6.2).

Discovers tables, columns, types, primary/foreign keys, relationships,
indexes, sample rows, and row counts from the connected database, and
returns them as the Pydantic models defined in `models.py`.

This is read-only introspection only — it never touches the "agent"
query path. Wrapped in tracing spans per the Phase 1 tracing bootstrap.
"""
from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from ai_database_agent.database.models import (
    ColumnSchema,
    DatabaseSchema,
    ForeignKeySchema,
    IndexSchema,
    TableSchema,
)
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)

DEFAULT_SAMPLE_ROWS = 3


class DatabaseInspector:
    """Introspects a SQLAlchemy Engine and produces a DatabaseSchema."""

    def __init__(self, engine: Engine, sample_row_count: int = DEFAULT_SAMPLE_ROWS):
        self._engine = engine
        self._sample_row_count = sample_row_count

    def inspect_database(self) -> DatabaseSchema:
        with _tracer.start_as_current_span("db.inspect_database") as span:
            inspector = inspect(self._engine)
            table_names = inspector.get_table_names()
            span.set_attribute("db.table_count", len(table_names))

            tables = [self._inspect_table(inspector, name) for name in table_names]
            return DatabaseSchema(dialect=self._engine.dialect.name, tables=tables)

    def _inspect_table(self, inspector, table_name: str) -> TableSchema:
        with _tracer.start_as_current_span("db.inspect_table") as span:
            span.set_attribute("db.table_name", table_name)

            pk_constraint = inspector.get_pk_constraint(table_name)
            primary_keys: list[str] = pk_constraint.get("constrained_columns") or []

            columns = [
                ColumnSchema(
                    name=col["name"],
                    type=str(col["type"]),
                    nullable=bool(col.get("nullable", True)),
                    is_primary_key=col["name"] in primary_keys,
                    default=(
                        str(col["default"]) if col.get("default") is not None else None
                    ),
                )
                for col in inspector.get_columns(table_name)
            ]

            foreign_keys = [
                ForeignKeySchema(
                    column=fk["constrained_columns"][0],
                    references_table=fk["referred_table"],
                    references_column=fk["referred_columns"][0],
                )
                for fk in inspector.get_foreign_keys(table_name)
                if fk.get("constrained_columns") and fk.get("referred_columns")
            ]

            indexes = [
                IndexSchema(
                    name=idx["name"] or f"{table_name}_idx",
                    columns=idx.get("column_names") or [],
                    unique=bool(idx.get("unique", False)),
                )
                for idx in inspector.get_indexes(table_name)
            ]

            row_count = self._get_row_count(table_name)
            sample_rows = self._get_sample_rows(table_name)

            return TableSchema(
                name=table_name,
                columns=columns,
                primary_keys=primary_keys,
                foreign_keys=foreign_keys,
                indexes=indexes,
                row_count=row_count,
                sample_rows=sample_rows,
            )

    def _get_row_count(self, table_name: str) -> int:
        # Identifiers can't be parameterized; table_name comes only from
        # inspector.get_table_names(), never from user/LLM input.
        with self._engine.connect() as conn:
            result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            return int(result.scalar_one())

    def _get_sample_rows(self, table_name: str) -> list[dict]:
        with self._engine.connect() as conn:
            result = conn.execute(
                text(f'SELECT * FROM "{table_name}" LIMIT :limit'),
                {"limit": self._sample_row_count},
            )
            return [dict(row._mapping) for row in result]
