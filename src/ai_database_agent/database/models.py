"""
Structured representation of a discovered database schema
(Phase 1, section 6.2 — DatabaseSchema -> TableSchema -> columns/keys/samples).

These are plain data models (no behavior beyond validation) produced
by `inspector.py` and consumed later by schema representation (Phase 2)
and retrieval (Phase 11+).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    name: str
    type: str
    nullable: bool
    is_primary_key: bool = False
    default: str | None = None


class ForeignKeySchema(BaseModel):
    column: str
    references_table: str
    references_column: str


class IndexSchema(BaseModel):
    name: str
    columns: list[str]
    unique: bool = False


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnSchema] = Field(default_factory=list)
    primary_keys: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeySchema] = Field(default_factory=list)
    indexes: list[IndexSchema] = Field(default_factory=list)
    row_count: int = 0
    sample_rows: list[dict] = Field(default_factory=list)


class DatabaseSchema(BaseModel):
    dialect: str
    tables: list[TableSchema] = Field(default_factory=list)

    def get_table(self, name: str) -> TableSchema | None:
        return next((t for t in self.tables if t.name == name), None)
