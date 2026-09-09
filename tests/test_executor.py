import pytest
from sqlalchemy import create_engine

from ai_database_agent.database.executor import QueryExecutor


def _executor():
    engine = create_engine("sqlite:///./data/concert_singer.sqlite", future=True)
    return QueryExecutor(engine)


# --- happy path ---

def test_simple_select_returns_results():
    r = _executor().execute("SELECT * FROM stadium")
    assert r.success
    assert r.row_count == 9
    assert "Name" in r.columns


def test_select_with_filter():
    r = _executor().execute("SELECT Name FROM singer WHERE Country = 'United States'")
    assert r.success
    assert r.row_count > 0
    assert all("Name" in row for row in r.rows)


def test_join_query():
    r = _executor().execute("""
        SELECT s.Name, c.concert_Name
        FROM singer s
        JOIN singer_in_concert sc ON s.Singer_ID = sc.Singer_ID
        JOIN concert c ON sc.concert_ID = c.concert_ID
        LIMIT 5
    """)
    assert r.success
    assert r.row_count <= 5
    assert "Name" in r.columns


def test_returns_execution_time():
    r = _executor().execute("SELECT 1")
    assert r.execution_ms >= 0


# --- security: read-only enforcement ---

def test_rejects_insert():
    r = _executor().execute("INSERT INTO singer (Name) VALUES ('Hacker')")
    assert not r.success
    assert "INSERT" in r.error


def test_rejects_drop():
    r = _executor().execute("DROP TABLE singer")
    assert not r.success
    assert "DROP" in r.error


def test_rejects_update():
    r = _executor().execute("UPDATE stadium SET Capacity = 0")
    assert not r.success
    assert "UPDATE" in r.error


def test_rejects_non_select():
    r = _executor().execute("DELETE FROM concert WHERE 1=1")
    assert not r.success


# --- error handling ---

def test_invalid_sql_returns_error_not_exception():
    r = _executor().execute("SELECT * FROM nonexistent_table_xyz")
    assert not r.success
    assert r.error is not None
    assert r.row_count == 0
