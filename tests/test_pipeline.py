from sqlalchemy import create_engine

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.validator import SQLValidator
from ai_database_agent.memory import Conversation


class _StubSQLGenerator:
    """Returns one fixed SQL string regardless of attempt history."""

    def __init__(self, sql):
        self._sql = sql
        self.calls = []
        self.conversation_calls = []

    def generate(self, question, schema_ddl, attempts=None, exemplars=None, conversation_turns=None):
        # Copy, since `attempts`/`conversation_turns` are mutable lists that
        # keep growing after this call returns.
        self.calls.append(list(attempts) if attempts else [])
        self.conversation_calls.append(list(conversation_turns) if conversation_turns else [])
        return self._sql


class _SequenceSQLGenerator:
    """Returns each SQL string in order on successive calls (Milestone 3 retries)."""

    def __init__(self, sqls):
        self._sqls = list(sqls)
        self.calls = []
        self.conversation_calls = []

    def generate(self, question, schema_ddl, attempts=None, exemplars=None, conversation_turns=None):
        self.calls.append(list(attempts) if attempts else [])
        self.conversation_calls.append(list(conversation_turns) if conversation_turns else [])
        return self._sqls[len(self.calls) - 1]


class _StubAnswerGenerator:
    def generate(self, question, sql, query_result):
        return f"Found {query_result.row_count} row(s)."


def _pipeline(sql, max_attempts=3):
    return _pipeline_with_generator(_StubSQLGenerator(sql), max_attempts=max_attempts)


def _pipeline_with_generator(sql_generator, max_attempts=3):
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    return AgentPipeline(
        engine=engine,
        sql_generator=sql_generator,
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


def test_ask_without_conversation_sends_no_conversation_turns():
    generator = _StubSQLGenerator("SELECT name FROM singer WHERE country = 'France'")
    _pipeline_with_generator(generator).ask("Which singers are from France?")

    assert generator.conversation_calls == [[]]


def test_ask_with_conversation_appends_successful_turn():
    generator = _StubSQLGenerator("SELECT name FROM singer WHERE country = 'France'")
    pipeline = _pipeline_with_generator(generator)
    conversation = Conversation()

    result = pipeline.ask("Which singers are from France?", conversation=conversation)

    assert result.success
    assert len(conversation.turns) == 1
    assert conversation.turns[0].question == "Which singers are from France?"
    assert conversation.turns[0].sql == "SELECT name FROM singer WHERE country = 'France'"
    assert conversation.turns[0].answer == result.answer


def test_ask_with_conversation_replays_prior_turns_into_generation():
    generator = _SequenceSQLGenerator(
        [
            "SELECT name FROM singer WHERE country = 'France'",
            "SELECT name FROM singer WHERE country = 'Canada'",
        ]
    )
    pipeline = _pipeline_with_generator(generator)
    conversation = Conversation()

    pipeline.ask("Which singers are from France?", conversation=conversation)
    pipeline.ask("What about from Canada?", conversation=conversation)

    # Second call was given the first turn's question/SQL as conversation history.
    assert len(generator.conversation_calls[1]) == 1
    assert generator.conversation_calls[1][0].question == "Which singers are from France?"
    assert generator.conversation_calls[1][0].sql == "SELECT name FROM singer WHERE country = 'France'"


def test_ask_with_conversation_does_not_record_a_failed_turn():
    generator = _StubSQLGenerator("DROP TABLE singer")
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    pipeline = AgentPipeline(
        engine=engine,
        sql_generator=generator,
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        max_attempts=1,
    )
    conversation = Conversation()

    result = pipeline.ask("Delete everything", conversation=conversation)

    assert not result.success
    assert conversation.turns == []
