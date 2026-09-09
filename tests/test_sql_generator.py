from ai_database_agent.llm.sql_generator import CorrectionAttempt, SQLGenerator


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


def test_extracts_plain_sql():
    generator = SQLGenerator(client=_FakeClient("SELECT * FROM singer"))
    sql = generator.generate("List all singers", "CREATE TABLE singer (...)")
    assert sql == "SELECT * FROM singer"


def test_extracts_sql_from_code_fence():
    generator = SQLGenerator(client=_FakeClient("```sql\nSELECT * FROM singer\n```"))
    sql = generator.generate("List all singers", "schema")
    assert sql == "SELECT * FROM singer"


def test_strips_sql_label_and_semicolon():
    generator = SQLGenerator(client=_FakeClient("SQL: SELECT * FROM singer;"))
    sql = generator.generate("List all singers", "schema")
    assert sql == "SELECT * FROM singer"


def test_sends_schema_and_question_to_llm():
    client = _FakeClient("SELECT 1")
    generator = SQLGenerator(client=client)
    generator.generate("How many singers?", "CREATE TABLE singer (...)")

    user_message = client.chat.completions.last_kwargs["messages"][1]["content"]
    assert "How many singers?" in user_message
    assert "CREATE TABLE singer" in user_message


def test_generate_with_no_attempts_sends_only_the_initial_turn():
    client = _FakeClient("SELECT 1")
    generator = SQLGenerator(client=client)
    generator.generate("How many singers?", "schema")

    assert len(client.chat.completions.last_kwargs["messages"]) == 2


def test_generate_replays_prior_attempts_as_conversation_turns():
    client = _FakeClient("SELECT COUNT(*) FROM singer")
    generator = SQLGenerator(client=client)
    attempts = [
        CorrectionAttempt(
            sql="SELECT COUNT(*) FROM singers",
            error="Query error: no such table: singers",
        )
    ]

    generator.generate("How many singers?", "schema", attempts=attempts)

    messages = client.chat.completions.last_kwargs["messages"]
    assert len(messages) == 4
    assert messages[2] == {"role": "assistant", "content": "SELECT COUNT(*) FROM singers"}
    assert "no such table: singers" in messages[3]["content"]


def test_generate_replays_multiple_attempts_in_order():
    client = _FakeClient("SELECT 1")
    generator = SQLGenerator(client=client)
    attempts = [
        CorrectionAttempt(sql="BAD SQL 1", error="error one"),
        CorrectionAttempt(sql="BAD SQL 2", error="error two"),
    ]

    generator.generate("question", "schema", attempts=attempts)

    messages = client.chat.completions.last_kwargs["messages"]
    assert len(messages) == 6
    assert messages[2]["content"] == "BAD SQL 1"
    assert "error one" in messages[3]["content"]
    assert messages[4]["content"] == "BAD SQL 2"
    assert "error two" in messages[5]["content"]
