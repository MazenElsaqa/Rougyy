"""Milestone 2 — evaluation dataset and harness (pulled forward from Phase 18)."""
from ai_database_agent.evaluation.dataset import EvalCase, get_default_dataset
from ai_database_agent.evaluation.harness import (
    EvalCaseResult,
    EvalReport,
    EvaluationHarness,
    rows_match,
)

__all__ = [
    "EvalCase",
    "get_default_dataset",
    "EvalCaseResult",
    "EvalReport",
    "EvaluationHarness",
    "rows_match",
]
