"""
Milestone 1 — thin end-to-end walking skeleton. Extended in Milestone 3
with a self-correction loop.

    question -> schema DDL -> LLM generates SQL -> AST validation ->
    read-only execution -> LLM writes a grounded answer

If validation rejects the SQL or execution fails, the error is fed
back to the SQL generator (see llm/sql_generator.py's `attempts`
history) and it gets another try, capped at MAX_ATTEMPTS total
attempts. This is the single highest-ROI accuracy feature identified
in the project review: most LLM-generated SQL mistakes are
self-evidently fixable once the actual DB error is visible (a typo'd
column name, a missing JOIN, an ambiguous reference), so one or two
retries recover a meaningful fraction of otherwise-failed questions
without any new subsystem (no RAG, no memory) required.

Still no RAG or memory here — those remain later milestones. On
exhausting all attempts, this returns an AgentResult with `error`
set to the last failure, plus `attempts` set to how many tries were
made, so the evaluation harness (Milestone 2) can track average
retries alongside accuracy.
"""
from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import Engine

from ai_database_agent.database.connection import get_engine
from ai_database_agent.database.executor import QueryExecutor, QueryResult
from ai_database_agent.database.inspector import DatabaseInspector
from ai_database_agent.database.validator import SQLValidator, ValidationResult
from ai_database_agent.llm.answer_generator import AnswerGenerator
from ai_database_agent.llm.sql_generator import CorrectionAttempt, SQLGenerator
from ai_database_agent.observability.tracing import get_tracer
from ai_database_agent.schema.formatter import SchemaFormatter

_tracer = get_tracer(__name__)

MAX_ATTEMPTS = 3


class AgentResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    question: str
    sql: str | None = None
    validation: ValidationResult | None = None
    query_result: QueryResult | None = None
    answer: str | None = None
    error: str | None = None
    attempts: int = 1

    @property
    def success(self) -> bool:
        return self.error is None


class AgentPipeline:
    """Wires schema context, LLM generation, validation, and execution into ask()."""

    def __init__(
        self,
        engine: Engine | None = None,
        sql_generator: SQLGenerator | None = None,
        answer_generator: AnswerGenerator | None = None,
        validator: SQLValidator | None = None,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self._engine = engine or get_engine()
        self._sql_generator = sql_generator or SQLGenerator()
        self._answer_generator = answer_generator or AnswerGenerator()
        self._validator = validator or SQLValidator()
        self._executor = QueryExecutor(self._engine)
        self._max_attempts = max_attempts
        self._schema_ddl: str | None = None  # lazily built, cached for this pipeline's lifetime

    def ask(self, question: str) -> AgentResult:
        with _tracer.start_as_current_span("agent.ask") as span:
            span.set_attribute("agent.question", question)

            schema_ddl = self._get_schema_ddl()
            history: list[CorrectionAttempt] = []
            last_sql: str | None = None
            last_validation: ValidationResult | None = None
            last_query_result: QueryResult | None = None

            for attempt_number in range(1, self._max_attempts + 1):
                sql = self._sql_generator.generate(question, schema_ddl, attempts=history)
                last_sql = sql or last_sql

                if not sql:
                    history.append(CorrectionAttempt(sql="", error="No SQL was returned."))
                    continue

                validation = self._validator.validate(sql)
                last_validation = validation
                if not validation.valid:
                    span.set_attribute("agent.rejected", True)
                    history.append(
                        CorrectionAttempt(
                            sql=sql,
                            error=f"Generated SQL failed validation: {validation.reason}",
                        )
                    )
                    continue

                query_result = self._executor.execute(sql)
                last_query_result = query_result
                if not query_result.success:
                    history.append(CorrectionAttempt(sql=sql, error=query_result.error or "Unknown error."))
                    continue

                answer = self._answer_generator.generate(question, sql, query_result)
                span.set_attribute("agent.attempts", attempt_number)
                return AgentResult(
                    question=question,
                    sql=sql,
                    validation=validation,
                    query_result=query_result,
                    answer=answer,
                    attempts=attempt_number,
                )

            span.set_attribute("agent.attempts", self._max_attempts)
            span.set_attribute("agent.exhausted_retries", True)
            last_error = history[-1].error if history else "Unknown error."
            return AgentResult(
                question=question,
                sql=last_sql,
                validation=last_validation,
                query_result=last_query_result,
                error=f"Failed after {self._max_attempts} attempt(s): {last_error}",
                attempts=self._max_attempts,
            )

    def _get_schema_ddl(self) -> str:
        if self._schema_ddl is None:
            schema = DatabaseInspector(self._engine).inspect_database()
            self._schema_ddl = SchemaFormatter(schema).to_ddl()
        return self._schema_ddl
