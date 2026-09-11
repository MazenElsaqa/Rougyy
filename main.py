"""
Entry point / demo for the phases and milestones implemented so far.

Three modes:
  python main.py                    -> Phase 1 demo: inspect the schema
                                        and print a summary.
  python main.py "your question"    -> Milestone 1: run one question
                                        through the full ask() pipeline
                                        (LLM generates SQL, it's
                                        validated, executed read-only,
                                        and answered). No memory across
                                        separate runs of this command.
  python main.py --chat             -> Milestone 5: an interactive REPL
                                        that keeps a Conversation across
                                        turns, so follow-ups like "what
                                        about just from Canada?" resolve
                                        against the previous turn.

Tracing (Phase 1) is bootstrapped first so every span from here on is
captured, whichever mode runs.
"""
from __future__ import annotations

import sys

from ai_database_agent.agent import AgentPipeline
from ai_database_agent.database import DatabaseInspector, get_engine
from ai_database_agent.memory import Conversation
from ai_database_agent.observability.logging import get_logger, setup_logging
from ai_database_agent.observability.tracing import get_tracer, setup_tracing

setup_logging()
setup_tracing()
tracer = get_tracer(__name__)
log = get_logger(__name__)


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
        log.info("cli.ask_demo.start", extra={"question": question})
        pipeline = AgentPipeline()
        try:
            result = pipeline.ask(question)
        except Exception:
            log.exception("cli.ask_demo.exception", extra={"question": question})
            raise

        print(f"Question: {result.question}\n")
        if result.sql:
            print(f"Generated SQL:\n  {result.sql}\n")

        if not result.success:
            log.error(
                "cli.ask_demo.failed",
                extra={"question": question, "sql": result.sql, "error": result.error, "attempts": result.attempts},
            )
            print(f"Error: {result.error}")
            return

        log.info(
            "cli.ask_demo.success",
            extra={"question": question, "sql": result.sql, "row_count": result.query_result.row_count},
        )
        print(f"Rows returned: {result.query_result.row_count}")
        print(f"Answer: {result.answer}")


def chat_demo() -> None:
    with tracer.start_as_current_span("main.chat_demo"):
        pipeline = AgentPipeline()
        conversation = Conversation()
        log.info("cli.chat_demo.start")

        print("Chat mode - type a question, or 'exit' / Ctrl-D to quit.")
        print("Conversation memory is kept across turns in this session.\n")

        while True:
            try:
                question = input("> ").strip()
            except EOFError:
                print()
                break
            if not question:
                continue
            if question.lower() in {"exit", "quit"}:
                break

            log.info("cli.chat_demo.turn.start", extra={"question": question, "turns_so_far": len(conversation.recent())})
            try:
                result = pipeline.ask(question, conversation=conversation)
            except Exception:
                log.exception("cli.chat_demo.turn.exception", extra={"question": question})
                print("  Error: something went wrong. See logs/errors.log for details.\n")
                continue

            if result.sql:
                print(f"  SQL: {result.sql}")
            if not result.success:
                log.error(
                    "cli.chat_demo.turn.failed",
                    extra={"question": question, "sql": result.sql, "error": result.error},
                )
                print(f"  Error: {result.error}\n")
                continue
            log.info("cli.chat_demo.turn.success", extra={"question": question, "sql": result.sql})
            print(f"  Answer: {result.answer}\n")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--chat":
        chat_demo()
    elif len(sys.argv) > 1:
        ask_demo(" ".join(sys.argv[1:]))
    else:
        inspect_demo()


if __name__ == "__main__":
    main()
