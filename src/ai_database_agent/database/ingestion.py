"""
CSV/Excel ingestion: turn a user's tabular file into a queryable SQLite database.

Design: the rest of the app (validation, execution, linking, SQL
generation) only speaks SQLAlchemy/SQLite, so instead of teaching it
new formats we convert at upload time. `ingest_tabular_upload()`
writes the file's tables into a fresh SQLite file, which then flows
through the exact same registry path as a native `.sqlite` upload --
zero changes downstream.

- CSV: stdlib only. Encoding tried as utf-8-sig -> cp1256 (common for
  Arabic Excel exports) -> latin-1 fallback; delimiter sniffed
  (, ; tab |) with comma fallback. First row is the header.
- Excel: openpyxl, `data_only=True` (cached values, never formulas).
  Every non-empty sheet becomes one table.
- Types per column: INTEGER -> REAL -> TEXT (dates stay ISO TEXT so
  string comparison/sorting keeps working). Mixed columns fall back
  to TEXT rather than losing data. Empty strings become NULL.
- Identifiers are sanitized (unicode letters kept, so Arabic names
  survive) and always double-quoted; duplicates get _2, _3...
- Safety: per-table row cap so one giant file can't blow up the server.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

MAX_ROWS_PER_TABLE = 100_000
_TYPE_SAMPLE_LIMIT = 1_000

_CSV_ENCODINGS = ("utf-8-sig", "cp1256", "windows-1252", "latin-1")
_CSV_DELIMITERS = [",", ";", "\t", "|"]


class IngestionError(ValueError):
    """Raised when a tabular file can't be turned into a database."""


@dataclass
class ImportedTable:
    name: str
    row_count: int


def sanitize_identifier(name: str, fallback: str) -> str:
    """Make a safe SQLite identifier, keeping unicode letters (Arabic OK)."""
    cleaned = unicodedata.normalize("NFKC", str(name or "")).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"[^\w]", "", cleaned, flags=re.UNICODE)
    cleaned = cleaned.strip("_")[:60] or fallback
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for name in names:
        key = name.lower()
        if key not in seen:
            seen[key] = 1
            out.append(name)
        else:
            seen[key] += 1
            out.append(f"{name}_{seen[key]}")
    return out


def _infer_text_type(values: list[str]) -> str:
    """INTEGER if every value parses as int, REAL if every value parses
    as float, else TEXT. Empty strings are ignored (become NULL)."""
    non_empty = [v for v in values if v != ""]
    if not non_empty:
        return "TEXT"
    try:
        for v in non_empty:
            int(v)
        return "INTEGER"
    except ValueError:
        pass
    try:
        for v in non_empty:
            float(v)
        return "REAL"
    except ValueError:
        pass
    return "TEXT"


def _convert(value: str, col_type: str):
    if value == "":
        return None
    if col_type == "INTEGER":
        return int(value)
    if col_type == "REAL":
        return float(value)
    return value


def _write_table(conn: sqlite3.Connection, table: str, columns: list[str], col_types: list[str], rows: list[list]) -> int:
    cols_ddl = ", ".join(f'"{c}" {t}' for c, t in zip(columns, col_types))
    conn.execute(f'CREATE TABLE "{table}" ({cols_ddl})')
    placeholders = ", ".join("?" * len(columns))
    col_list = ", ".join(f'"{c}"' for c in columns)
    converted = [[_convert(str(v) if v is not None else "", t) for v, t in zip(row, col_types)] for row in rows]
    conn.executemany(f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})', converted)
    return len(converted)


def _decode_csv(source: Path) -> tuple[str, str]:
    raw = source.read_bytes()
    if not raw.strip():
        raise IngestionError("The CSV file is empty.")
    last_error: Exception | None = None
    for encoding in _CSV_ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except (UnicodeDecodeError, ValueError) as exc:
            last_error = exc
    raise IngestionError(f"Could not decode the CSV file (tried {', '.join(_CSV_ENCODINGS)}).") from last_error


def ingest_csv(source: Path, conn: sqlite3.Connection, table_name: str) -> ImportedTable:
    text, _ = _decode_csv(source)
    try:
        dialect = csv.Sniffer().sniff(text[:32_768], delimiters="".join(_CSV_DELIMITERS))
    except csv.Error:
        dialect = csv.excel  # plain comma-separated fallback
    reader = csv.reader(text.splitlines(), dialect)
    all_rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not all_rows:
        raise IngestionError("The CSV file has no data rows.")
    header, *data = all_rows
    if not data:
        raise IngestionError("The CSV file has no data rows (only a header).")
    columns = _dedupe(
        [sanitize_identifier(h, f"column_{i + 1}") for i, h in enumerate(header)]
    )
    width = len(columns)
    data = [([(row[i].strip() if i < len(row) else "") for i in range(width)]) for row in data]
    data = data[:MAX_ROWS_PER_TABLE]
    col_types = [
        _infer_text_type([row[i] for row in data[:_TYPE_SAMPLE_LIMIT]]) for i in range(width)
    ]
    count = _write_table(conn, table_name, columns, col_types, data)
    return ImportedTable(name=table_name, row_count=count)


def _excel_cell(value):
    import datetime

    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return str(value).strip()


def ingest_excel(source: Path, conn: sqlite3.Connection, name_prefix: str) -> list[ImportedTable]:
    try:
        import openpyxl
    except ImportError as exc:
        raise IngestionError("Excel support needs the 'openpyxl' package.") from exc
    try:
        workbook = openpyxl.load_workbook(source, data_only=True, read_only=True)
    except Exception as exc:
        raise IngestionError(f"Could not open the Excel file: {exc}") from exc

    imported: list[ImportedTable] = []
    used_names: set[str] = set()
    try:
        for sheet in workbook.worksheets:
            grid = [[_excel_cell(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
            grid = [row for row in grid if any(cell != "" for cell in row)]
            if len(grid) < 2:  # need a header plus at least one data row
                continue
            header, *data = grid
            columns = _dedupe(
                [sanitize_identifier(h, f"column_{i + 1}") for i, h in enumerate(header)]
            )
            width = len(columns)
            data = [[row[i] if i < len(row) else "" for i in range(width)] for row in data]
            data = data[:MAX_ROWS_PER_TABLE]
            col_types = [
                _infer_text_type([row[i] for row in data[:_TYPE_SAMPLE_LIMIT]]) for i in range(width)
            ]
            base = sanitize_identifier(f"{name_prefix}_{sheet.title}", f"sheet_{len(imported) + 1}")
            table = base
            suffix = 2
            while table.lower() in used_names:
                table = f"{base}_{suffix}"
                suffix += 1
            used_names.add(table.lower())
            count = _write_table(conn, table, columns, col_types, data)
            imported.append(ImportedTable(name=table, row_count=count))
    finally:
        workbook.close()

    if not imported:
        raise IngestionError("The Excel file has no sheets with data (need a header row plus data).")
    return imported


def ingest_tabular_upload(source: Path, display_name: str, dest: Path) -> list[ImportedTable]:
    """Convert a .csv/.xls/.xlsx file into a SQLite database at `dest`.
    Returns the imported tables. Raises IngestionError on any problem."""
    suffix = source.suffix.lower()
    if suffix not in (".csv", ".xls", ".xlsx"):
        raise IngestionError(f"Unsupported tabular type '{suffix}'. Use .csv, .xls, or .xlsx.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    table_base = sanitize_identifier(display_name, "uploaded")
    conn = sqlite3.connect(str(dest))
    try:
        if suffix == ".csv":
            imported = [ingest_csv(source, conn, table_base)]
        else:
            imported = ingest_excel(source, conn, table_base)
        conn.commit()
    except Exception:
        conn.close()
        dest.unlink(missing_ok=True)
        raise
    conn.close()
    return imported
