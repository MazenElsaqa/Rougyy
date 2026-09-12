"""Tabular ingestion: CSV (incl. Arabic cp1256) and multi-sheet Excel."""

import sqlite3

import pytest

from ai_database_agent.database.ingestion import (
    IngestionError,
    ingest_tabular_upload,
    sanitize_identifier,
)


def _read_table(dest, table):
    conn = sqlite3.connect(str(dest))
    try:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
        rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
        return cols, rows
    finally:
        conn.close()


def test_csv_basic_with_type_inference(tmp_path):
    src = tmp_path / "singers.csv"
    src.write_text("name,age,country\nJustin,30,France\nRose,25,Canada\n", encoding="utf-8")
    dest = tmp_path / "out.sqlite"

    imported = ingest_tabular_upload(src, "singers", dest)

    assert len(imported) == 1
    assert imported[0].name == "singers"
    assert imported[0].row_count == 2
    cols, rows = _read_table(dest, "singers")
    assert cols == ["name", "age", "country"]
    assert rows[0] == ("Justin", 30, "France")  # age inferred INTEGER


def test_csv_arabic_cp1256_encoding(tmp_path):
    src = tmp_path / "singers.csv"
    src.write_bytes("الاسم,البلد\nأحمد,مصر\nليلى,فرنسا\n".encode("cp1256"))
    dest = tmp_path / "out.sqlite"

    imported = ingest_tabular_upload(src, "singers", dest)

    assert imported[0].row_count == 2
    cols, rows = _read_table(dest, imported[0].name)
    assert cols == ["الاسم", "البلد"]  # Arabic identifiers survive
    assert rows[0] == ("أحمد", "مصر")


def test_csv_semicolon_delimiter_and_mixed_types(tmp_path):
    src = tmp_path / "data.csv"
    src.write_text("item;price;note\npen;1.5;cheap\nbook;12;good\n", encoding="utf-8")
    dest = tmp_path / "out.sqlite"

    imported = ingest_tabular_upload(src, "data", dest)

    cols, rows = _read_table(dest, "data")
    assert cols == ["item", "price", "note"]
    assert rows[0][1] == pytest.approx(1.5)  # REAL inference


def test_excel_multi_sheet_becomes_multi_table(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    src = tmp_path / "bands.xlsx"
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Singers"
    ws1.append(["name", "age"])
    ws1.append(["Justin", 30])
    ws2 = wb.create_sheet("Concerts")
    ws2.append(["title", "year"])
    ws2.append(["Rock Night", 2014])
    wb.save(src)
    wb.close()
    dest = tmp_path / "out.sqlite"

    imported = ingest_tabular_upload(src, "bands", dest)

    assert {t.name for t in imported} == {"bands_Singers", "bands_Concerts"}
    _, rows = _read_table(dest, "bands_Singers")
    assert rows == [("Justin", 30)]


def test_empty_and_garbage_files_rejected(tmp_path):
    dest = tmp_path / "out.sqlite"
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(IngestionError):
        ingest_tabular_upload(empty, "empty", dest)

    header_only = tmp_path / "header.csv"
    header_only.write_text("a,b,c\n", encoding="utf-8")
    with pytest.raises(IngestionError):
        ingest_tabular_upload(header_only, "header", dest)

    fake = tmp_path / "fake.xlsx"
    fake.write_bytes(b"this is not an excel file")
    with pytest.raises(IngestionError):
        ingest_tabular_upload(fake, "fake", dest)


def test_unsupported_suffix_rejected(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("hello", encoding="utf-8")
    with pytest.raises(IngestionError):
        ingest_tabular_upload(src, "notes", tmp_path / "out.sqlite")


def test_sanitize_identifier():
    assert sanitize_identifier("First Name!", "x") == "First_Name"
    assert sanitize_identifier("123abc", "x") == "_123abc"
    assert sanitize_identifier("  ", "fallback") == "fallback"
    assert sanitize_identifier("المغني", "x") == "المغني"
