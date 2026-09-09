"""
Entry point / demo for the phases and milestones implemented so far.

Two modes:
  python main.py                    -> Phase 1 demo: inspect the schema
                                        and print a summary.
  python main.py "your question"    -> Milestone 1: run the full
                                        ask() pipeline (LLM generates
                                        SQL, it's validated, executed
                                        read-only, and answered).

Tracing (Phase 1) is bootstrapped first so every span from here on is
captured, whichever mode runs.
"""
from __future__ import annotations

import sys

from ai_database_agent.agent import AgentPipeline
from ai_database_agent.database import DatabaseInspector, get_engine
from ai_database_agent.observability.tracing import get_tracer, setup_tracing

setup_tracing()
tracer = get_tracer(__name__)


def inspect_demo() -> None:
    with tracer.start_as_current_span("main.inspect_demo"):
        engine = get_engine()
        schema = DatabaseInspector(engine).inspect_database()

        print(f"Dialect: {schema.dialect}")
        print(f"Tables discovered: {len(schema.tables)}\n")

        for table in schema.tables:
            print(f"- {table.name} ({table.row_count} rows)")
            pk = ", ".join(table.primary_keys) or "none"
            print(f"    primary key: {pk}")
            for fk in table.foreign_keys:
                print(
                    f"    fk: {fk.column} -> {fk.references_table}.{fk.references_column}"
                )
            col_names = ", ".join(c.name for c in table.columns)
            print(f"    columns: {col_names}")


def ask_demo(question: str) -> None:
    with tracer.start_as_current_span("main.ask_demo"):
        pipeline = AgentPipeline()
        result = pipeline.ask(question)

        print(f"Question: {result.question}\n")
        if result.sql:
            print(f"Generated SQL:\n  {result.sql}\n")

        if not result.success:
            print(f"Error: {result.error}")
            return

        print(f"Rows returned: {result.query_result.row_count}")
        print(f"Answer: {result.answer}")


def main() -> None:
    if len(sys.argv) > 1:
        ask_demo(" ".join(sys.argv[1:]))
    else:
        inspect_demo()


if __name__ == "__main__":
    main()
