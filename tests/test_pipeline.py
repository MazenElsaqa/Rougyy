from sqlalchemy import create_engine

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.validator import SQLValidator


class _StubSQLGenerator:
    """Returns one fixed SQL string regardless of attempt history."""

    def __init__(self, sql):
        self._sql = sql
        self.calls = []

    def generate(self, question, schema_ddl, attempts=None):
        # Copy, since `attempts` is the pipeline's mutable history list and
        # keeps growing after this call returns.
        self.calls.append(list(attempts) if attempts else [])
        return self._sql


class _SequenceSQLGenerator:
    """Returns each SQL string in order on successive calls (Milestone 3 retries)."""

    def __init__(self, sqls):
        self._sqls = list(sqls)
        self.calls = []

    def generate(self, question, schema_ddl, attempts=None):
        self.calls.append(list(attempts) if attempts else [])
        return self._sqls[len(self.calls) - 1]


class _StubAnswerGenerator:
    def generate(self, question, sql, query_result):
        return f"Found {query_result.row_count} row(s)."


def _pipeline(sql, max_attempts=3):
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    return AgentPipeline(
        engine=engine,
        sql_generator=_StubSQLGenerator(sql),
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        max_attempts=max_attempts,
    )


def test_ask_happy_path_returns_grounded_answer():
    result = _pipeline("SELECT name FROM singer WHERE country = 'France'").ask(
        "Which singers are from France?"
    )

    assert result.success
    assert result.query_result.row_count == 3
    assert result.answer == "Found 3 row(s)."
    assert result.attempts == 1


def test_ask_rejects_unsafe_sql_and_retries_until_attempts_exhausted():
    generator = _StubSQLGenerator("DROP TABLE singer")
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    pipeline = AgentPipeline(
        engine=engine,
        sql_generator=generator,
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        max_attempts=2,
    )

    result = pipeline.ask("Delete everything")

    assert not result.success
    assert result.query_result is None  # never reached the executor
    assert result.validation is not None
    assert not result.validation.valid
    assert result.attempts == 2
    assert len(generator.calls) == 2
    # Second call was given the first attempt's error as feedback.
    assert len(generator.calls[1]) == 1
    assert "DROP TABLE singer" == generator.calls[1][0].sql


def test_ask_surfaces_execution_errors_after_exhausting_retries():
    generator = _StubSQLGenerator("SELECT * FROM nonexistent_table_xyz")
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    pipeline = AgentPipeline(
        engine=engine,
        sql_generator=generator,
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        max_attempts=3,
    )

    result = pipeline.ask("bad question")

    assert not result.success
    assert result.query_result is not None
    assert not result.query_result.success
    assert result.attempts == 3
    assert len(generator.calls) == 3


def test_ask_self_corrects_and_succeeds_on_a_later_attempt():
    generator = _SequenceSQLGenerator(
        [
            "SELECT name FROM singers WHERE country = 'France'",  # wrong table name
            "SELECT name FROM singer WHERE country = 'France'",  # corrected
        ]
    )
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    pipeline = AgentPipeline(
        engine=engine,
        sql_generator=generator,
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        max_attempts=3,
    )

    result = pipeline.ask("Which singers are from France?")

    assert result.success
    assert result.attempts == 2
    assert result.query_result.row_count == 3
    # The second generate() call received the first failure as feedback.
    assert len(generator.calls[1]) == 1
    assert "no such table" in generator.calls[1][0].error.lower()


def test_ask_stops_retrying_as_soon_as_a_valid_result_is_returned():
    generator = _StubSQLGenerator("SELECT name FROM singer WHERE country = 'France'")
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    pipeline = AgentPipeline(
        engine=engine,
        sql_generator=generator,
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        max_attempts=3,
    )

    outcome = pipeline.ask("Which singers are from France?")

    assert outcome.success
    assert outcome.attempts == 1
    assert len(generator.calls) == 1
