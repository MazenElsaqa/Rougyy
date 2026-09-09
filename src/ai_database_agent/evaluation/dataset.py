"""
Milestone 2 — evaluation dataset.

A small held-out set of (question, gold SQL) pairs for the
`concert_singer` demo database, in the same spirit as the Spider
benchmark's execution-accuracy evaluation: each gold query is run
against the real database and its result set is compared to
whatever SQL the pipeline generates, so the metric measures whether
the *data returned* is correct — not whether the SQL text matches
token-for-token.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    question: str
    gold_sql: str
    tags: list[str] = Field(default_factory=list)


def get_default_dataset() -> list[EvalCase]:
    """The concert_singer eval set used as Milestone 2's regression gate."""
    return [
        EvalCase(
            question="How many singers are there?",
            gold_sql="SELECT COUNT(*) FROM singer",
            tags=["aggregation"],
        ),
        EvalCase(
            question="What are the names of singers from France?",
            gold_sql="SELECT Name FROM singer WHERE Country = 'France'",
            tags=["filter"],
        ),
        EvalCase(
            question="What is the average age of singers from France?",
            gold_sql="SELECT AVG(Age) FROM singer WHERE Country = 'France'",
            tags=["aggregation", "filter"],
        ),
        EvalCase(
            question="What are the names of all stadiums, ordered by capacity from highest to lowest?",
            gold_sql="SELECT Name FROM stadium ORDER BY Capacity DESC",
            tags=["order_by"],
        ),
        EvalCase(
            question="What is the name of the stadium with the highest capacity?",
            gold_sql="SELECT Name FROM stadium ORDER BY Capacity DESC LIMIT 1",
            tags=["order_by", "limit"],
        ),
        EvalCase(
            question="How many concerts happened in 2014?",
            gold_sql="SELECT COUNT(*) FROM concert WHERE Year = 2014",
            tags=["aggregation", "filter"],
        ),
        EvalCase(
            question="What are the names of concerts along with the name of the stadium they were held in?",
            gold_sql=(
                "SELECT concert.concert_Name, stadium.Name "
                "FROM concert JOIN stadium ON concert.Stadium_ID = stadium.Stadium_ID"
            ),
            tags=["join"],
        ),
        EvalCase(
            question="How many singers performed in each concert?",
            gold_sql="SELECT concert_ID, COUNT(*) FROM singer_in_concert GROUP BY concert_ID",
            tags=["join", "group_by"],
        ),
        EvalCase(
            question="What are the names of singers who performed in concert 1?",
            gold_sql=(
                "SELECT singer.Name FROM singer "
                "JOIN singer_in_concert ON singer.Singer_ID = singer_in_concert.Singer_ID "
                "WHERE singer_in_concert.concert_ID = 1"
            ),
            tags=["join", "filter"],
        ),
        EvalCase(
            question="What are the distinct countries singers come from?",
            gold_sql="SELECT DISTINCT Country FROM singer",
            tags=["distinct"],
        ),
        EvalCase(
            question="What is the total capacity of all stadiums combined?",
            gold_sql="SELECT SUM(Capacity) FROM stadium",
            tags=["aggregation"],
        ),
        EvalCase(
            question="What are the names of concerts held in stadiums with a capacity greater than 10000?",
            gold_sql=(
                "SELECT concert.concert_Name FROM concert "
                "JOIN stadium ON concert.Stadium_ID = stadium.Stadium_ID "
                "WHERE stadium.Capacity > 10000"
            ),
            tags=["join", "filter"],
        ),
    ]
