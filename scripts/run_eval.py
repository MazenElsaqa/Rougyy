"""
Milestone 2 — run the evaluation harness from the command line.

    python scripts/run_eval.py

Runs every case in the default eval dataset through the real
AgentPipeline (this calls the configured LLM — set OPENAI_API_KEY,
and OPENAI_BASE_URL/LLM_MODEL if not using OpenAI directly, in .env
first) against the concert_singer database, and prints a per-case
breakdown plus the aggregate metrics that gate every milestone after
this one.
"""
from __future__ import annotations

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.connection import get_engine
from ai_database_agent.database.executor import QueryExecutor
from ai_database_agent.evaluation.dataset import get_default_dataset
from ai_database_agent.evaluation.harness import EvaluationHarness
from ai_database_agent.observability.tracing import setup_tracing


def main() -> None:
    setup_tracing()

    engine = get_engine()
    pipeline = AgentPipeline(engine=engine)
    gold_executor = QueryExecutor(engine)
    harness = EvaluationHarness(pipeline, gold_executor)

    dataset = get_default_dataset()
    report = harness.run(dataset)

    for result in report.results:
        status = "PASS" if result.execution_match else "FAIL"
        print(f"[{status}] {result.question}")
        print(f"    gold:      {result.gold_sql}")
        print(f"    generated: {result.generated_sql}")
        if result.error:
            print(f"    error:     {result.error}")
        print(f"    latency:   {result.latency_ms} ms\n")

    print("=" * 40)
    print(report.summary())


if __name__ == "__main__":
    main()
