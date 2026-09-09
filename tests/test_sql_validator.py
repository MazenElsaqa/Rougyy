from ai_database_agent.database.validator import SQLValidator


def _validator():
    return SQLValidator()


# --- happy path ---

def test_valid_select_passes():
    result = _validator().validate("SELECT name FROM singer WHERE country = 'France'")
    assert result.valid
    assert result.reason is None


def test_valid_join_passes():
    sql = """
        SELECT s.name, c.concert_name
        FROM singer s
        JOIN singer_in_concert sc ON s.singer_id = sc.singer_id
        JOIN concert c ON sc.concert_id = c.concert_id
    """
    assert _validator().validate(sql).valid


def test_strips_trailing_semicolon():
    assert _validator().validate("SELECT 1;").valid


# --- security: structural rejection ---

def test_rejects_insert():
    result = _validator().validate("INSERT INTO singer (name) VALUES ('Hacker')")
    assert not result.valid


def test_rejects_drop():
    result = _validator().validate("DROP TABLE singer")
    assert not result.valid


def test_rejects_update():
    result = _validator().validate("UPDATE stadium SET capacity = 0")
    assert not result.valid


def test_rejects_delete():
    result = _validator().validate("DELETE FROM concert WHERE 1=1")
    assert not result.valid


def test_rejects_multiple_statements():
    result = _validator().validate("SELECT 1; DROP TABLE singer;")
    assert not result.valid
    assert result.statement_count == 2


def test_rejects_pragma_and_attach():
    assert not _validator().validate("PRAGMA table_info(singer)").valid
    assert not _validator().validate("ATTACH DATABASE 'evil.db' AS evil").valid


# --- error handling ---

def test_rejects_invalid_sql():
    result = _validator().validate("SELEKT * FROM singer")
    assert not result.valid
    assert result.reason is not None


def test_rejects_empty_sql():
    result = _validator().validate("")
    assert not result.valid
