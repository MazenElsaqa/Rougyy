from ai_database_agent.database.executor import QueryResult
from ai_database_agent.llm.answer_generator import AnswerGenerator


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


def test_generates_answer_from_rows():
    client = _FakeClient("Three singers are from France.")
    generator = AnswerGenerator(client=client)
    result = QueryResult(
        sql="SELECT name FROM singer WHERE country = 'France'",
        success=True,
        columns=["name"],
        rows=[{"name": "Justin Brown"}, {"name": "Rose White"}, {"name": "John Nizinik"}],
        row_count=3,
        execution_ms=1,
    )

    answer = generator.generate("How many singers are from France?", result.sql, result)

    assert answer == "Three singers are from France."
    user_message = client.chat.completions.last_kwargs["messages"][1]["content"]
    assert "France" in user_message
    assert "Justin Brown" in user_message


def test_reports_zero_rows_faithfully():
    client = _FakeClient("No matching results were found.")
    generator = AnswerGenerator(client=client)
    result = QueryResult(
        sql="SELECT name FROM singer WHERE country = 'Mars'",
        success=True,
        columns=["name"],
        rows=[],
        row_count=0,
        execution_ms=1,
    )

    answer = generator.generate("Which singers are from Mars?", result.sql, result)

    assert "no" in answer.lower()
    user_message = client.chat.completions.last_kwargs["messages"][1]["content"]
    assert "Row count: 0" in user_message


def test_defaults_to_answer_model_not_sql_model(monkeypatch):
    from ai_database_agent.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    monkeypatch.setenv("OLLAMA_ANSWER_MODEL", "qwen3.5:4b-mlx")
    try:
        generator = AnswerGenerator(client=_FakeClient("ok"))
        assert generator._model == "qwen3.5:4b-mlx"
    finally:
        get_settings.cache_clear()
