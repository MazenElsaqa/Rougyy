from sqlalchemy import create_engine

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.validator import SQLValidator


class _StubSQLGenerator:
    def __init__(self, sql):
        self._sql = sql

    def generate(self, question, schema_ddl):
        return self._sql


class _StubAnswerGenerator:
    def generate(self, question, sql, query_result):
        return f"Found {query_result.row_count} row(s)."


def _pipeline(sql):
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    return AgentPipeline(
        engine=engine,
        sql_generator=_StubSQLGenerator(sql),
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
    )


def test_ask_happy_path_returns_grounded_answer():
    result = _pipeline("SELECT name FROM singer WHERE country = 'France'").ask(
        "Which singers are from France?"
    )

    assert result.success
    assert result.query_result.row_count == 3
    assert result.answer == "Found 3 row(s)."


def test_ask_rejects_unsafe_sql_before_it_ever_executes():
    result = _pipeline("DROP TABLE singer").ask("Delete everything")

    assert not result.success
    assert result.query_result is None  # never reached the executor
    assert result.validation is not None
    assert not result.validation.valid


def test_ask_surfaces_execution_errors():
    result = _pipeline("SELECT * FROM nonexistent_table_xyz").ask("bad question")

    assert not result.success
    assert result.query_result is not None
    assert not result.query_result.success
