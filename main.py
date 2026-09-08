"""
Entry point / demo for the phases implemented so far.

Currently demonstrates Phase 1: connect to the configured database,
run the inspector, and print a summary of the discovered schema.
Tracing (also Phase 1) is bootstrapped first so every span from here
on is captured.
"""
from ai_database_agent.database import DatabaseInspector, get_engine
from ai_database_agent.observability.tracing import get_tracer, setup_tracing

setup_tracing()
tracer = get_tracer(__name__)


def main() -> None:
    with tracer.start_as_current_span("main.run"):
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


if __name__ == "__main__":
    main()
