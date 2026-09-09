"""
Milestone 4 — few-shot exemplars.

A small set of curated (question, SQL) pairs for the concert_singer
schema, used to show the LLM the expected style -- explicit column
names, standard JOIN syntax, no SELECT * -- through worked examples
rather than instructions alone. Few-shot exemplars are one of the
most reliable, lowest-cost accuracy levers in text-to-SQL (see
DAIL-SQL): 2-4 examples in-context typically beat a longer list of
rules in the system prompt.

Deliberately distinct from the Milestone 2 evaluation dataset (both
in question phrasing and in which columns/patterns they exercise) so
the exemplars don't hand the harness's own answers to the model.
"""
from __future__ import annotations

from pydantic import BaseModel


class SQLExemplar(BaseModel):
    question: str
    sql: str


def get_default_exemplars() -> list[SQLExemplar]:
    return [
        SQLExemplar(
            question="How many stadiums are there?",
            sql="SELECT COUNT(*) FROM stadium",
        ),
        SQLExemplar(
            question="What are the names and ages of singers, from youngest to oldest?",
            sql="SELECT Name, Age FROM singer ORDER BY Age ASC",
        ),
        SQLExemplar(
            question="What is the name of the singer with the most concert appearances?",
            sql=(
                "SELECT singer.Name FROM singer "
                "JOIN singer_in_concert ON singer.Singer_ID = singer_in_concert.Singer_ID "
                "GROUP BY singer.Singer_ID ORDER BY COUNT(*) DESC LIMIT 1"
            ),
        ),
        SQLExemplar(
            question="What are the different themes used across all concerts?",
            sql="SELECT DISTINCT Theme FROM concert",
        ),
    ]
