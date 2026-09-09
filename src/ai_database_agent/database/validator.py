"""
AST-based SQL validation (folds Phase 4 into Milestone 1).

The executor (Phase 3) already rejects mutating statements with a
string/keyword check. This module adds a second, independent layer
using a real SQL parser (sqlglot) so validation doesn't rely on
keyword matching alone — it inspects the actual parsed statement
tree, which is much harder to sneak a mutation past (e.g. via a CTE,
a stacked statement, or unusual formatting).

This is deliberately a *safety* gate, not a correctness gate: it
answers "is this statement structurally safe to run?", not "is this
the right SQL for the question?".
"""
from __future__ import annotations

import sqlglot
from pydantic import BaseModel
from sqlglot import exp

# Any of these appearing anywhere in the parsed statement causes rejection.
# exp.Command catches generic/unparsed statements like PRAGMA, ATTACH, VACUUM.
_FORBIDDEN_EXPRESSIONS: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
)


class ValidationResult(BaseModel):
    valid: bool
    reason: str | None = None
    statement_count: int = 0


class SQLValidator:
    """Validates that a SQL string is a single, safe, read-only SELECT."""

    def __init__(self, dialect: str = "sqlite"):
        self._dialect = dialect

    def validate(self, sql: str) -> ValidationResult:
        cleaned = (sql or "").strip().rstrip(";").strip()
        if not cleaned:
            return ValidationResult(valid=False, reason="Empty SQL.")

        try:
            statements = [s for s in sqlglot.parse(cleaned, read=self._dialect) if s is not None]
        except Exception as exc:  # sqlglot raises its own ParseError subclasses
            return ValidationResult(valid=False, reason=f"SQL failed to parse: {exc}")

        if len(statements) != 1:
            return ValidationResult(
                valid=False,
                reason=f"Expected exactly one statement, found {len(statements)}.",
                statement_count=len(statements),
            )

        statement = statements[0]
        if not isinstance(statement, exp.Select):
            return ValidationResult(
                valid=False,
                reason=f"Only SELECT statements are allowed, found {type(statement).__name__}.",
            )

        for node in statement.walk():
            # sqlglot's Expression.walk() yields the node itself in modern
            # versions; guard against older versions that yield tuples.
            candidate = node[0] if isinstance(node, tuple) else node
            if isinstance(candidate, _FORBIDDEN_EXPRESSIONS):
                return ValidationResult(
                    valid=False,
                    reason=f"Statement contains forbidden operation: {type(candidate).__name__}.",
                )

        return ValidationResult(valid=True, statement_count=1)
