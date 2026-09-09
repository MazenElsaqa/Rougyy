"""
Milestone 1 — thin end-to-end walking skeleton.

    question -> schema DDL -> LLM generates SQL -> AST validation ->
    read-only execution -> LLM writes a grounded answer

Deliberately the simplest possible path that proves every layer is
wired together correctly end to end. No RAG, no memory, and no
self-correction retries yet (those are later milestones) — on any
failure this returns an AgentResult with `error` set rather than
retrying, so behavior stays easy to reason about and to measure
against an evaluation harness (Milestone 2).
"""
from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import Engine

from ai_database_agent.database.connection import get_engine
from ai_database_agent.database.executor import QueryExecutor, QueryResult
from ai_database_agent.database.inspector import DatabaseInspector
from ai_database_agent.database.validator import SQLValidator, ValidationResult
from ai_database_agent.llm.answer_generator import AnswerGenerator
from ai_database_agent.llm.sql_generator import SQLGenerator
from ai_database_agent.observability.tracing import get_tracer
from ai_database_agent.schema.formatter import SchemaFormatter

_tracer = get_tracer(__name__)


class AgentResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    question: str
    sql: str | None = None
    validation: ValidationResult | None = None
    query_result: QueryResult | None = None
    answer: str | None = None
    error: str | None = None

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
    ):
        self._engine = engine or get_engine()
        self._sql_generator = sql_generator or SQLGenerator()
        self._answer_generator = answer_generator or AnswerGenerator()
        self._validator = validator or SQLValidator()
        self._executor = QueryExecutor(self._engine)
        self._schema_ddl: str | None = None  # lazily built, cached for this pipeline's lifetime

    def ask(self, question: str) -> AgentResult:
        with _tracer.start_as_current_span("agent.ask") as span:
            span.set_attribute("agent.question", question)

            schema_ddl = self._get_schema_ddl()

            sql = self._sql_generator.generate(question, schema_ddl)
            if not sql:
                return AgentResult(question=question, error="The LLM did not return any SQL.")

            validation = self._validator.validate(sql)
            if not validation.valid:
                span.set_attribute("agent.rejected", True)
                return AgentResult(
                    question=question,
                    sql=sql,
                    validation=validation,
                    error=f"Generated SQL failed validation: {validation.reason}",
                )

            query_result = self._executor.execute(sql)
            if not query_result.success:
                return AgentResult(
                    question=question,
                    sql=sql,
                    validation=validation,
                    query_result=query_result,
                    error=query_result.error,
                )

            answer = self._answer_generator.generate(question, sql, query_result)
            return AgentResult(
                question=question,
                sql=sql,
                validation=validation,
                query_result=query_result,
                answer=answer,
            )

    def _get_schema_ddl(self) -> str:
        if self._schema_ddl is None:
            schema = DatabaseInspector(self._engine).inspect_database()
            self._schema_ddl = SchemaFormatter(schema).to_ddl()
        return self._schema_ddl
