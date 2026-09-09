"""
Creates the local SQLite databases used by this project's demos and tests.

Two databases are built:
  data/concert_singer.sqlite  - the full demo dataset (the classic
                                 "concert_singer" schema/data used across
                                 Text-to-SQL research), used by main.py,
                                 the executor, schema formatter, and the
                                 Milestone 1 agent pipeline.
  data/_smoke_test.sqlite     - a minimal schema used only by the
                                 connection/inspector unit tests.

Both files are gitignored (see .gitignore) and can be regenerated at
any time:

    python scripts/setup_db.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def build_concert_singer_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE stadium (
                Stadium_ID INTEGER PRIMARY KEY,
                Location   TEXT NOT NULL,
                Name       TEXT NOT NULL,
                Capacity   INTEGER NOT NULL,
                Highest    INTEGER,
                Lowest     INTEGER,
                Average    INTEGER
            );

            CREATE TABLE singer (
                Singer_ID INTEGER PRIMARY KEY,
                Name      TEXT NOT NULL,
                Country   TEXT NOT NULL,
                Song_Name TEXT,
                Age       INTEGER
            );

            CREATE TABLE concert (
                concert_ID   INTEGER PRIMARY KEY,
                concert_Name TEXT NOT NULL,
                Theme        TEXT,
                Stadium_ID   INTEGER NOT NULL,
                Year         INTEGER NOT NULL,
                FOREIGN KEY (Stadium_ID) REFERENCES stadium (Stadium_ID)
            );
            CREATE INDEX idx_concert_year ON concert (Year);

            CREATE TABLE singer_in_concert (
                concert_ID INTEGER NOT NULL,
                Singer_ID  INTEGER NOT NULL,
                PRIMARY KEY (concert_ID, Singer_ID),
                FOREIGN KEY (concert_ID) REFERENCES concert (concert_ID),
                FOREIGN KEY (Singer_ID) REFERENCES singer (Singer_ID)
            );
            """
        )

        conn.executemany(
            "INSERT INTO stadium VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "Raith Rovers", "Stark's Park", 10104, 4812, 1294, 2106),
                (2, "Ayr United", "Somerset Park", 11998, 2363, 1057, 1477),
                (3, "East Fife", "Bayview Stadium", 2000, 1980, 533, 864),
                (4, "Queen's Park", "Hampden Park", 52500, 1763, 466, 730),
                (5, "Stirling Albion", "Forthbank Stadium", 3808, 1125, 404, 642),
                (6, "Arbroath", "Gayfield Park", 4125, 921, 411, 638),
                (7, "Alloa Athletic", "Recreation Park", 3100, 1057, 331, 637),
                (8, "Peterhead", "Balmoor", 4000, 837, 400, 615),
                (9, "Brechin City", "Glebe Park", 3960, 780, 315, 552),
            ],
        )

        conn.executemany(
            "INSERT INTO singer VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Joe Sharp", "Netherlands", "You", 52),
                (2, "Timbaland", "United States", "Flat", 32),
                (3, "Justin Brown", "France", "Hey", 29),
                (4, "Rose White", "France", "Sun", 41),
                (5, "John Nizinik", "France", "Gentleman", 43),
                (6, "Tribal King", "United States", "Love", 25),
            ],
        )

        conn.executemany(
            "INSERT INTO concert VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Auditions", "Free choice", 1, 2014),
                (2, "Super bootcamp", "Free choice 2", 2, 2014),
                (3, "Home Visits", "Bleeding Love", 2, 2015),
                (4, "Week 1", "Wide Awake", 9, 2014),
                (5, "Week 2", "Party All Night", 7, 2015),
                (6, "Week 3", "Happy Tonight", 3, 2015),
            ],
        )

        conn.executemany(
            "INSERT INTO singer_in_concert VALUES (?, ?)",
            [
                (1, 2), (1, 3), (1, 5),
                (2, 1), (2, 4),
                (3, 3), (3, 6),
                (4, 2), (4, 5),
            ],
        )

        conn.commit()
    finally:
        conn.close()


def build_smoke_test_db(path: Path) -> None:
    """A tiny schema used only by the connection/inspector unit tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE stadium (
                stadium_id INTEGER PRIMARY KEY,
                name       TEXT NOT NULL
            );

            CREATE TABLE singer (
                singer_id INTEGER PRIMARY KEY,
                name      TEXT NOT NULL,
                country   TEXT NOT NULL,
                age       INTEGER
            );

            CREATE TABLE concert (
                concert_id INTEGER PRIMARY KEY,
                stadium_id INTEGER NOT NULL,
                year       INTEGER NOT NULL,
                FOREIGN KEY (stadium_id) REFERENCES stadium (stadium_id)
            );
            CREATE INDEX idx_concert_year ON concert (year);
            """
        )

        conn.executemany(
            "INSERT INTO stadium VALUES (?, ?)",
            [(1, "Test Arena"), (2, "Test Dome")],
        )
        conn.executemany(
            "INSERT INTO singer VALUES (?, ?, ?, ?)",
            [(1, "Test Singer", "Testland", 30)],
        )
        conn.executemany(
            "INSERT INTO concert VALUES (?, ?, ?)",
            [(1, 1, 2020)],
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    concert_singer_path = DATA_DIR / "concert_singer.sqlite"
    smoke_test_path = DATA_DIR / "_smoke_test.sqlite"

    build_concert_singer_db(concert_singer_path)
    build_smoke_test_db(smoke_test_path)

    print(f"Created {concert_singer_path}")
    print(f"Created {smoke_test_path}")


if __name__ == "__main__":
    main()
