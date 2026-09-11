"""Intent gate: greetings get chat replies, data questions keep the pipeline."""

from sqlalchemy import create_engine

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.validator import SQLValidator
from ai_database_agent.llm.answer_generator import AnswerGenerator
from ai_database_agent.llm.intent import CHAT, DATA_QUERY, IntentClassifier, looks_like_small_talk


class _ExplodingCompletions:
    def create(self, **kwargs):
        raise AssertionError("LLM should not have been called")


class _ExplodingChat:
    completions = _ExplodingCompletions()


class _ExplodingClient:
    """Fails any LLM call -- proves the heuristic path needs no model."""

    chat = _ExplodingChat()


class _FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, content):
                self.message = _Msg(content)

        class _Resp:
            def __init__(self, content):
                self.choices = [_Choice(content)]

        return _Resp(self._content)


class _FakeClient:
    def __init__(self, content):
        self.chat = type("C", (), {"completions": _FakeCompletions(content)})()


class _StubAnswerGenerator(AnswerGenerator):
    def __init__(self):
        self._client = _FakeClient("canned")
        self._model = "test-model"

    def generate_chat_reply(self, question, table_names=None, conversation_turns=None):
        return f"Chat reply to: {question}"

    def generate_unanswerable_reply(self, question, table_names=None):
        return f"Cannot answer from data: {question}"


class _ExplodingSQLGenerator:
    def generate(self, *args, **kwargs):
        raise AssertionError("SQL generation should not have been called")


class _StubClassifier:
    def __init__(self, intent):
        self._intent = intent
        self.calls = 0

    def classify(self, question, table_names=None, conversation_turns=None):
        self.calls += 1
        return self._intent


def _pipeline(sql_generator, classifier):
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    return AgentPipeline(
        engine=engine,
        sql_generator=sql_generator,
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        intent_classifier=classifier,
        max_attempts=3,
    )


def test_heuristic_catches_greetings_without_llm():
    classifier = IntentClassifier(client=_ExplodingClient())
    for greeting in [
        "hi", "Hi!", "hey", "hello", "how are you today?", "How are you?",
        "thanks", "thanks!", "thank you", "who are you?", "what can you do?",
        "bye", "مرحبا", "اهلا", "السلام عليكم", "عامل ايه؟", "شكرا",
        "صباح الخير", "انت مين؟",
    ]:
        assert classifier.classify(greeting) == CHAT, greeting


def test_heuristic_passes_data_questions_to_llm():
    assert not looks_like_small_talk("How many singers are there?")
    assert not looks_like_small_talk("hi, how many singers are from France?")
    assert not looks_like_small_talk("List all concerts in 2014 please")
    classifier = IntentClassifier(client=_FakeClient("DATA_QUERY"))
    assert classifier.classify("How many singers are there?") == DATA_QUERY


def test_llm_intent_parsing_and_fail_open():
    assert IntentClassifier(client=_FakeClient("chat")).classify("...?") == CHAT
    assert IntentClassifier(client=_FakeClient("  data_query ")).classify("...?") == DATA_QUERY
    assert IntentClassifier(client=_FakeClient("I am not sure")).classify("...?") == DATA_QUERY
    assert IntentClassifier(client=_FakeClient("")).classify("...?") == DATA_QUERY


def test_pipeline_chat_skips_sql_generation():
    pipeline = _pipeline(_ExplodingSQLGenerator(), _StubClassifier(CHAT))
    result = pipeline.ask("how are you today?")

    assert result.success
    assert result.intent == CHAT
    assert result.sql is None
    assert result.attempts == 0
    assert result.answer == "Chat reply to: how are you today?"


def test_pipeline_accepts_preclassified_intent_without_reclassifying():
    classifier = _StubClassifier(CHAT)
    pipeline = _pipeline(_ExplodingSQLGenerator(), classifier)
    pipeline.ask("anything at all", intent=CHAT)

    assert classifier.calls == 0


def test_pipeline_sentinel_stops_early_with_explanation():
    class _SentinelGenerator:
        def __init__(self):
            self.calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            return "SELECT NULL WHERE 1=0"

    generator = _SentinelGenerator()
    pipeline = _pipeline(generator, _StubClassifier(DATA_QUERY))
    result = pipeline.ask("What is the meaning of life?")

    assert result.success
    assert result.answer == "Cannot answer from data: What is the meaning of life?"
    assert result.attempts == 1
    assert generator.calls == 1  # no retries burned
