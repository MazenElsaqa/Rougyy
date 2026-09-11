from sqlalchemy import create_engine

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.executor import QueryExecutor
from ai_database_agent.database.validator import SQLValidator
from ai_database_agent.evaluation.dataset import EvalCase
from ai_database_agent.evaluation.harness import EvaluationHarness, rows_match
from ai_database_agent.llm.intent import DATA_QUERY


class _MapSQLGenerator:
    """Stub that returns a fixed SQL string per question, from a dict."""

    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping

    def generate(self, question, schema_ddl, attempts=None, exemplars=None, conversation_turns=None):
        return self._mapping.get(question)


class _StubAnswerGenerator:
    def generate(self, question, sql, query_result):
        return f"Found {query_result.row_count} row(s)."


class _StubClassifier:
    def classify(self, question, table_names=None, conversation_turns=None):
        return DATA_QUERY


def _harness(mapping: dict[str, str]) -> EvaluationHarness:
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    pipeline = AgentPipeline(
        engine=engine,
        sql_generator=_MapSQLGenerator(mapping),
        answer_generator=_StubAnswerGenerator(),
        validator=SQLValidator(),
        intent_classifier=_StubClassifier(),
    )
    gold_executor = QueryExecutor(engine)
    return EvaluationHarness(pipeline, gold_executor)


def test_execution_match_when_generated_sql_equals_gold_sql():
    case = EvalCase(question="How many singers are there?", gold_sql="SELECT COUNT(*) FROM singer")
    harness = _harness({case.question: case.gold_sql})

    report = harness.run([case])

    assert report.total == 1
    assert report.execution_accuracy == 1.0
    result = report.results[0]
    assert result.valid_sql
    assert result.executed
    assert result.execution_match


def test_execution_match_when_generated_sql_differs_but_returns_same_data():
    case = EvalCase(
        question="What are the names of singers from France?",
        gold_sql="SELECT Name FROM singer WHERE Country = 'France'",
    )
    # Different alias and join phrasing than the gold SQL, same underlying rows.
    generated = "SELECT singer.Name AS Name FROM singer WHERE singer.Country = 'France'"
    harness = _harness({case.question: generated})

    report = harness.run([case])

    assert report.results[0].execution_match


def test_execution_mismatch_when_generated_sql_returns_wrong_data():
    case = EvalCase(question="How many singers are there?", gold_sql="SELECT COUNT(*) FROM singer")
    harness = _harness({case.question: "SELECT COUNT(*) FROM stadium"})

    report = harness.run([case])

    result = report.results[0]
    assert result.executed
    assert not result.execution_match
    assert report.execution_accuracy == 0.0


def test_invalid_sql_is_recorded_and_not_executed():
    case = EvalCase(question="Delete everything", gold_sql="SELECT 1")
    harness = _harness({case.question: "DROP TABLE singer"})

    report = harness.run([case])

    result = report.results[0]
    assert not result.valid_sql
    assert not result.executed
    assert not result.execution_match
    assert result.error is not None


def test_missing_sql_generation_is_recorded():
    case = EvalCase(question="unanswerable", gold_sql="SELECT 1")
    harness = _harness({})  # mapping.get returns None -> pipeline reports no SQL

    report = harness.run([case])

    result = report.results[0]
    assert result.generated_sql is None
    assert not result.valid_sql
    assert result.error is not None


def test_report_aggregate_metrics_average_across_cases():
    cases = [
        EvalCase(question="q1", gold_sql="SELECT COUNT(*) FROM singer"),
        EvalCase(question="q2", gold_sql="SELECT COUNT(*) FROM singer"),
    ]
    mapping = {
        "q1": "SELECT COUNT(*) FROM singer",  # matches gold
        "q2": "SELECT COUNT(*) FROM stadium",  # valid + executes, wrong data
    }
    harness = _harness(mapping)

    report = harness.run(cases)

    assert report.total == 2
    assert report.valid_sql_rate == 1.0
    assert report.execution_success_rate == 1.0
    assert report.execution_accuracy == 0.5


def test_rows_match_is_order_independent():
    gold = [{"Name": "A"}, {"Name": "B"}]
    pred = [{"Name": "B"}, {"Name": "A"}]
    assert rows_match(gold, pred)


def test_rows_match_detects_different_data():
    gold = [{"Name": "A"}]
    pred = [{"Name": "B"}]
    assert not rows_match(gold, pred)
