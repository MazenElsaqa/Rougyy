"""
Milestone 2 — evaluation harness.

Runs the AgentPipeline against a dataset of (question, gold SQL)
pairs and measures execution accuracy: whether the rows returned by
the LLM-generated SQL match the rows returned by the gold SQL,
executed against the same live database. This mirrors the Spider
benchmark's execution-accuracy metric — it scores the *data*
returned, not whether the generated SQL text matches the gold SQL
token-for-token, so semantically equivalent queries (different
aliases, column order, join order) still count as correct.

This harness is the regression gate every milestone after M2 is
measured against (see MILESTONES.md) — nothing here is a phase in
the original 40+ phase plan by number; it corresponds to pulling
Phase 18 (Evaluation) forward from far down the roadmap, right after
the first working pipeline (Milestone 1) instead of after a dozen
more phases.

Tracked per case:      valid SQL, execution success, execution match, latency
Tracked in aggregate:  valid-SQL rate, execution-success rate,
                        execution accuracy, average latency
"""
from __future__ import annotations

import time
from typing import Any, Callable

from pydantic import BaseModel

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.executor import QueryExecutor
from ai_database_agent.evaluation.dataset import EvalCase
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)


class EvalCaseResult(BaseModel):
    question: str
    gold_sql: str
    generated_sql: str | None = None
    valid_sql: bool = False
    executed: bool = False
    execution_match: bool = False
    latency_ms: float = 0.0
    error: str | None = None


class EvalReport(BaseModel):
    results: list[EvalCaseResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def valid_sql_rate(self) -> float:
        return _rate(self.results, lambda r: r.valid_sql)

    @property
    def execution_success_rate(self) -> float:
        return _rate(self.results, lambda r: r.executed)

    @property
    def execution_accuracy(self) -> float:
        return _rate(self.results, lambda r: r.execution_match)

    @property
    def avg_latency_ms(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(r.latency_ms for r in self.results) / len(self.results), 2)

    def summary(self) -> str:
        return "\n".join(
            [
                f"Cases:              {self.total}",
                f"Valid SQL rate:     {self.valid_sql_rate:.0%}",
                f"Execution success:  {self.execution_success_rate:.0%}",
                f"Execution accuracy: {self.execution_accuracy:.0%}",
                f"Avg latency:        {self.avg_latency_ms} ms",
            ]
        )


def _rate(results: list[EvalCaseResult], predicate: Callable[[EvalCaseResult], bool]) -> float:
    if not results:
        return 0.0
    return sum(1 for r in results if predicate(r)) / len(results)


def rows_match(gold_rows: list[dict[str, Any]], pred_rows: list[dict[str, Any]]) -> bool:
    """Order- and column-name-independent comparison of two result sets.

    Mirrors Spider's execution-accuracy metric: what matters is
    whether the same *data* came back, not whether column aliases,
    row ordering, or SQL text match. Values are stringified before
    comparing so e.g. `52` and `"52"` from different drivers still
    match.
    """

    def normalize(rows: list[dict[str, Any]]) -> list[tuple[str, ...]]:
        return sorted(tuple(str(v) for v in row.values()) for row in rows)

    return normalize(gold_rows) == normalize(pred_rows)


class EvaluationHarness:
    """Runs a dataset of eval cases through a pipeline and scores it."""

    def __init__(self, pipeline: AgentPipeline, gold_executor: QueryExecutor):
        self._pipeline = pipeline
        self._gold_executor = gold_executor

    def run(self, dataset: list[EvalCase]) -> EvalReport:
        with _tracer.start_as_current_span("evaluation.run") as span:
            span.set_attribute("evaluation.case_count", len(dataset))
            results = [self._run_case(case) for case in dataset]
            return EvalReport(results=results)

    def _run_case(self, case: EvalCase) -> EvalCaseResult:
        with _tracer.start_as_current_span("evaluation.case") as span:
            span.set_attribute("evaluation.question", case.question)

            t0 = time.perf_counter()
            agent_result = self._pipeline.ask(case.question)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = EvalCaseResult(
                question=case.question,
                gold_sql=case.gold_sql,
                generated_sql=agent_result.sql,
                latency_ms=latency_ms,
            )

            if agent_result.sql is None:
                result.error = agent_result.error
                return result

            result.valid_sql = bool(agent_result.validation and agent_result.validation.valid)
            if not result.valid_sql:
                result.error = agent_result.error
                return result

            if agent_result.query_result is None or not agent_result.query_result.success:
                result.error = agent_result.error
                return result

            result.executed = True

            gold_result = self._gold_executor.execute(case.gold_sql)
            if not gold_result.success:
                result.error = f"Gold SQL failed to execute: {gold_result.error}"
                return result

            result.execution_match = rows_match(gold_result.rows, agent_result.query_result.rows)
            span.set_attribute("evaluation.execution_match", result.execution_match)
            return result
