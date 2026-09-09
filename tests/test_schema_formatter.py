from sqlalchemy import create_engine

from ai_database_agent.database.inspector import DatabaseInspector
from ai_database_agent.schema.formatter import SchemaFormatter


def _get_formatter():
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    schema = DatabaseInspector(engine, sample_row_count=2).inspect_database()
    return SchemaFormatter(schema)


def test_to_ddl_contains_all_tables():
    ddl = _get_formatter().to_ddl()
    for table in ["stadium", "singer", "concert", "singer_in_concert"]:
        assert f"CREATE TABLE {table}" in ddl


def test_to_ddl_contains_primary_keys():
    ddl = _get_formatter().to_ddl()
    assert "PRIMARY KEY" in ddl


def test_to_ddl_contains_foreign_keys():
    ddl = _get_formatter().to_ddl()
    assert "FOREIGN KEY" in ddl
    assert "REFERENCES" in ddl


def test_to_ddl_contains_sample_rows():
    ddl = _get_formatter().to_ddl(include_samples=True)
    assert "Sample rows" in ddl
    assert "Stark" in ddl  # stadium name from real data


def test_to_ddl_no_samples_when_disabled():
    ddl = _get_formatter().to_ddl(include_samples=False)
    assert "Sample rows" not in ddl


def test_to_compact_one_line_per_table():
    compact = _get_formatter().to_compact()
    lines = [l for l in compact.strip().splitlines() if l]
    assert len(lines) == 4


def test_to_compact_contains_fk_info():
    compact = _get_formatter().to_compact()
    assert "FK:" in compact


def test_table_names_returns_all_four():
    names = _get_formatter().table_names()
    assert set(names) == {"stadium", "singer", "concert", "singer_in_concert"}
