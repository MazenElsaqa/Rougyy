from ai_database_agent.llm.sql_generator import SQLGenerator


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
