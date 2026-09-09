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

Milestone 4 adds lightweight schema linking (see schema/linker.py):
before generation, the full schema is narrowed to the tables actually
relevant to the question (plus their FK-connected join partners), and
augmented with real distinct values for small categorical columns.
This keeps the prompt smaller and steers the model away from
plausible-but-wrong table/column/value guesses -- without a vector
store, since concert_singer's 4 tables don't need one yet. A handful
of few-shot (question, SQL) exemplars (see llm/exemplars.py) are also
included on every attempt to demonstrate the expected output style.

On exhausting all attempts, this returns an AgentResult with `error`
set to the last failure, plus `attempts` set to how many tries were
made, so the evaluation harness (Milestone 2) can track average
retries alongside accuracy.

Milestone 5 adds optional conversation memory (see
memory/conversation.py): if a `Conversation` is passed to `ask()`,
recent turns' text is folded into schema linking (so a follow-up
that shares no words with the current schema still pulls in the
tables the conversation has been about), and the turns' (question,
sql) pairs are replayed into every generation attempt so a follow-up
like "what about just from Canada?" resolves against what was
actually already asked. On success, the turn is appended in place to
the same `Conversation` object the caller passed in, so it is ready
to reuse on the next `ask()` call without any extra bookkeeping.
"""
from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import Engine

from ai_database_agent.database.connection import get_engine
from ai_database_agent.database.executor import QueryExecutor, QueryResult
from ai_database_agent.database.inspector import DatabaseInspector
from ai_database_agent.database.models import DatabaseSchema
from ai_database_agent.database.validator import SQLValidator, ValidationResult
from ai_database_agent.llm.answer_generator import AnswerGenerator
from ai_database_agent.llm.exemplars import SQLExemplar, get_default_exemplars
from ai_database_agent.llm.sql_generator import CorrectionAttempt, SQLGenerator
from ai_database_agent.memory.conversation import Conversation
from ai_database_agent.observability.tracing import get_tracer
from ai_database_agent.schema.formatter import SchemaFormatter
from ai_database_agent.schema.linker import SchemaLinker

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
    linked_tables: list[str] = []

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
        linker: SchemaLinker | None = None,
        exemplars: list[SQLExemplar] | None = None,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self._engine = engine or get_engine()
        self._sql_generator = sql_generator or SQLGenerator()
        self._answer_generator = answer_generator or AnswerGenerator()
        self._validator = validator or SQLValidator()
        self._executor = QueryExecutor(self._engine)
        self._linker = linker or SchemaLinker(self._engine)
        self._exemplars = exemplars if exemplars is not None else get_default_exemplars()
        self._max_attempts = max_attempts
        self._full_schema: DatabaseSchema | None = None  # lazily built, cached for this pipeline's lifetime

    def ask(self, question: str, conversation: Conversation | None = None) -> AgentResult:
        with _tracer.start_as_current_span("agent.ask") as span:
            span.set_attribute("agent.question", question)

            conversation_turns = conversation.recent() if conversation else []
            span.set_attribute("agent.conversation_turns", len(conversation_turns))

            linking_text = question
            if conversation and not conversation.is_empty():
                linking_text = f"{conversation.context_text()} {question}"

            linked_schema = self._linker.link(linking_text, self._get_full_schema())
            value_hints = self._linker.value_hints(linked_schema)
            schema_ddl = SchemaFormatter(linked_schema).to_ddl_with_value_hints(value_hints)
            linked_tables = [t.name for t in linked_schema.tables]
            span.set_attribute("agent.linked_tables", ",".join(linked_tables))

            history: list[CorrectionAttempt] = []
            last_sql: str | None = None
            last_validation: ValidationResult | None = None
            last_query_result: QueryResult | None = None

            for attempt_number in range(1, self._max_attempts + 1):
                sql = self._sql_generator.generate(
                    question,
                    schema_ddl,
                    attempts=history,
                    exemplars=self._exemplars,
                    conversation_turns=conversation_turns,
                )
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
                if conversation is not None:
                    conversation.add_turn(question, sql, answer)
                return AgentResult(
                    question=question,
                    sql=sql,
                    validation=validation,
                    query_result=query_result,
                    answer=answer,
                    attempts=attempt_number,
                    linked_tables=linked_tables,
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
                linked_tables=linked_tables,
            )

    def _get_full_schema(self) -> DatabaseSchema:
        if self._full_schema is None:
            self._full_schema = DatabaseInspector(self._engine).inspect_database()
        return self._full_schema
