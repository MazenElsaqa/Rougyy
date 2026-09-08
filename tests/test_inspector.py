from sqlalchemy import create_engine

from ai_database_agent.database.inspector import DatabaseInspector
from ai_database_agent.database.models import DatabaseSchema


def _make_engine():
    return create_engine("sqlite:///./data/_smoke_test.sqlite", future=True)


def test_inspect_database_discovers_all_tables():
    engine = _make_engine()
    schema = DatabaseInspector(engine).inspect_database()

    assert isinstance(schema, DatabaseSchema)
    table_names = {t.name for t in schema.tables}
    assert {"stadium", "singer", "concert"} <= table_names


def test_inspect_table_discovers_columns_and_primary_key():
    engine = _make_engine()
    schema = DatabaseInspector(engine).inspect_database()

    singer = schema.get_table("singer")
    assert singer is not None
    assert singer.primary_keys == ["singer_id"]
    column_names = {c.name for c in singer.columns}
    assert column_names == {"singer_id", "name", "country", "age"}


def test_inspect_table_discovers_foreign_keys():
    engine = _make_engine()
    schema = DatabaseInspector(engine).inspect_database()

    concert = schema.get_table("concert")
    assert concert is not None
    assert len(concert.foreign_keys) == 1
    fk = concert.foreign_keys[0]
    assert fk.column == "stadium_id"
    assert fk.references_table == "stadium"
    assert fk.references_column == "stadium_id"


def test_inspect_table_discovers_index():
    engine = _make_engine()
    schema = DatabaseInspector(engine).inspect_database()

    concert = schema.get_table("concert")
    assert any("year" in idx.columns for idx in concert.indexes)


def test_inspect_table_row_count_and_sample_rows():
    engine = _make_engine()
    schema = DatabaseInspector(engine, sample_row_count=1).inspect_database()

    stadium = schema.get_table("stadium")
    assert stadium.row_count == 2
    assert len(stadium.sample_rows) == 1
    assert "name" in stadium.sample_rows[0]
