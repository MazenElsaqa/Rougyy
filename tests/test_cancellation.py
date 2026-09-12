"""Cooperative cancellation: a flagged session stops before any LLM call."""

from sqlalchemy import create_engine

from ai_database_agent.agent.cancellation import (
    cancel_session,
    clear_session,
    is_cancelled,
)
from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.validator import SQLValidator
from ai_database_agent.llm.intent import DATA_QUERY


class _CancelMidRunGenerator:
    """Fails the first attempt, then flags the session cancelled --
    simulating a user hitting Cancel while attempt 1 is in flight."""

    def __init__(self, session_id):
        self._session_id = session_id
        self.calls = 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        cancel_session(self._session_id)
        return "SELECT * FROM nonexistent_table_xyz"


class _StubClassifier:
    def classify(self, question, table_names=None, conversation_turns=None):
        return DATA_QUERY


class _MapSQLGenerator:
    def __init__(self, sql):
        self._sql = sql

    def generate(self, *args, **kwargs):
        return self._sql


class _StubAnswerGenerator:
    def generate(self, question, sql, query_result):
        return "answer"


def _pipeline(sql_generator):
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    return AgentPipeline(
        engine=engine,
        sql_generator=sql_generator,
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        intent_classifier=_StubClassifier(),
        max_attempts=3,
    )


def test_cancel_flag_roundtrip():
    clear_session("sess-x")
    assert not is_cancelled("sess-x")
    assert not is_cancelled(None)
    cancel_session("sess-x")
    assert is_cancelled("sess-x")
    clear_session("sess-x")
    assert not is_cancelled("sess-x")


def test_cancelled_ask_returns_cancelled_without_further_generating():
    generator = _CancelMidRunGenerator("sess-cancelled")
    try:
        result = _pipeline(generator).ask("How many singers are there?", session_id="sess-cancelled")
    finally:
        clear_session("sess-cancelled")

    assert not result.success
    assert result.error == "Cancelled."
    assert generator.calls == 1  # loop stopped before attempt 2


def test_fresh_ask_clears_stale_cancel_flag():
    # A cancel from an abandoned run must never block the next question.
    cancel_session("sess-stale")
    result = _pipeline(_MapSQLGenerator("SELECT COUNT(*) FROM singer")).ask(
        "How many singers are there?", session_id="sess-stale"
    )

    assert result.success
    assert not is_cancelled("sess-stale")


def test_cancel_does_not_record_a_turn():
    from ai_database_agent.memory import Conversation

    generator = _CancelMidRunGenerator("sess-norecord")
    try:
        pipeline = _pipeline(generator)
        conversation = Conversation()
        pipeline.ask("How many singers are there?", conversation=conversation, session_id="sess-norecord")
    finally:
        clear_session("sess-norecord")

    assert conversation.is_empty()
