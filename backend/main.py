"""
Milestone 6 — serving layer: FastAPI backend.

Wraps `AgentPipeline` (Milestones 1-5) in an HTTP API for the React
chat UI in `frontend/react-app/`. Runs as its own Vercel service (see
the root `vercel.json`) with its own dependency set; it reaches the
core `ai_database_agent` package by adding the repo's `src/` directory
to `sys.path` rather than depending on it as an installed package,
since each service in `experimentalServices` builds an isolated
environment from its own `pyproject.toml` and has no visibility into
the root project's editable install.

Conversation memory (Milestone 5) is kept per session: the client
generates a `session_id` on first load and sends it on every
subsequent request. It's keyed to a `Conversation` held in a
process-local dict and persisted per-turn to `data/app_state.sqlite`
(Milestone 12), so a backend restart resumes recent turns instead of
forgetting them. Uploaded databases persist the same way (see
`database/registry.py::reload_from_disk`).

Routes are defined without the `/api` prefix (e.g. `/health`, not
`/api/health`) because Vercel strips `routePrefix` before forwarding
to this service.
"""
from __future__ import annotations

import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import tempfile

import fastapi
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_database_agent.agent.cancellation import cancel_session
from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.executor import QueryExecutor
from ai_database_agent.database.inspector import DatabaseInspector
from ai_database_agent.database.ingestion import IngestionError, ingest_tabular_upload
from ai_database_agent.database.validator import SQLValidator
from ai_database_agent.database.registry import (
    DEFAULT_DB_ID,
    DatabaseRegistry,
    InvalidDatabaseFileError,
)
from ai_database_agent.llm.answer_generator import AnswerGenerator
from ai_database_agent.llm.client import check_ollama_connection, llm_connection_info
from ai_database_agent.llm.intent import CHAT, DATA_QUERY, IntentClassifier
from ai_database_agent.memory.conversation import Conversation
from ai_database_agent.observability.logging import get_logger, setup_logging
from ai_database_agent.observability.tracing import get_tracer, setup_tracing
from ai_database_agent.storage.state_store import StateStore

setup_logging(log_dir=_ROOT / "logs")
setup_tracing()
_tracer = get_tracer(__name__)
_log = get_logger(__name__)

_state_store = StateStore(_ROOT / "data" / "app_state.sqlite")


@asynccontextmanager
async def _lifespan(_: fastapi.FastAPI):
    """Milestone 12: on startup, re-register previously uploaded
    databases from disk so they reappear without re-uploading."""
    reloaded = _registry.reload_from_disk()
    _log.info("backend.startup", extra={"reloaded_databases": reloaded})
    yield


app = fastapi.FastAPI(title="DIDA Agent API", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: fastapi.Request, call_next):
    """Log every request/response with timing, and any unhandled exception
    with a full traceback, so a failure in the field can be traced back to
    the exact request and stack frame from logs/errors.log alone."""
    import time

    start = time.perf_counter()
    _log.info(
        "http.request.start",
        extra={"method": request.method, "path": request.url.path},
    )
    try:
        response = await call_next(request)
    except Exception:
        _log.exception(
            "http.request.unhandled_exception",
            extra={"method": request.method, "path": request.url.path},
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    _log.info(
        "http.request.end",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response

_registry = DatabaseRegistry(upload_dir=_ROOT / "data" / "uploads", state_store=_state_store)

# Shared, stateless helpers: one intent classification per question
# (not one per database in fan-out), and one chat replier.
_intent_classifier = IntentClassifier()
_chat_answerer = AnswerGenerator()
_conversations: dict[str, Conversation] = {}
_conversations_lock = Lock()

_pipelines: dict[str, AgentPipeline] = {}
_pipelines_lock = Lock()


def _get_conversation(session_id: str) -> Conversation:
    with _conversations_lock:
        conversation = _conversations.get(session_id)
        if conversation is None:
            # Milestone 12: resume recent turns from disk when this
            # session talked to a previous process lifetime.
            conversation = Conversation.resume(session_id, _state_store)
            _conversations[session_id] = conversation
        return conversation


def _get_pipeline(db_id: str) -> AgentPipeline:
    """One AgentPipeline per database (Milestone 7/8): each pipeline
    caches its own schema, schema-linker, and executor tied to a
    specific Engine, so switching databases must not reuse another
    database's pipeline.
    """
    with _pipelines_lock:
        pipeline = _pipelines.get(db_id)
        if pipeline is None:
            engine = _registry.get_engine(db_id)
            pipeline = AgentPipeline(engine=engine)
            _pipelines[db_id] = pipeline
        return pipeline


def _resolve_db_ids(requested: list[str] | None) -> list[str]:
    """None or empty -> every registered database ("search all at once").
    Otherwise, the caller's explicit selection, validated against the
    registry so a stale/unknown db_id fails clearly instead of silently.
    """
    if not requested:
        return [entry.id for entry in _registry.list_databases()]
    for db_id in requested:
        try:
            _registry.get(db_id)
        except KeyError:
            raise fastapi.HTTPException(status_code=404, detail=f"Unknown database id: {db_id}") from None
    return requested


# --- Request/response models ---------------------------------------------


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None
    # Milestone 8: which database(s) to run this question against.
    # None/empty = search every registered database at once.
    database_ids: list[str] | None = None


class SessionRequest(BaseModel):
    session_id: str


class DatabaseOut(BaseModel):
    id: str
    name: str
    dialect: str
    is_default: bool


class DatabaseListResponse(BaseModel):
    databases: list[DatabaseOut]


class QueryResultOut(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
    execution_ms: float


class SqlExecuteRequest(BaseModel):
    """Hand-written SQL to run as-is (no LLM involved)."""

    sql: str
    # Which database to run against; defaults to the default database.
    # The UI sends the currently selected one (its "USE ...").
    db_id: str | None = None


class SqlExecuteResponse(BaseModel):
    database_id: str
    database_name: str
    sql: str
    columns: list[str] = []
    rows: list[dict] = []
    row_count: int = 0
    truncated: bool = False
    execution_ms: float = 0.0
    error: str | None = None


class PerDatabaseAskResult(BaseModel):
    database_id: str
    database_name: str
    sql: str | None = None
    answer: str | None = None
    error: str | None = None
    attempts: int
    linked_tables: list[str]
    query_result: QueryResultOut | None = None


class AskResponse(BaseModel):
    session_id: str
    question: str
    sql: str | None = None
    answer: str | None = None
    error: str | None = None
    attempts: int
    linked_tables: list[str]
    query_result: QueryResultOut | None = None
    # Milestone 8: one entry per database this question was run against.
    # Length 1 for the common single-database case.
    per_database: list[PerDatabaseAskResult] = []
    # Intent gate: CHAT replies skip SQL entirely.
    intent: str = DATA_QUERY

    @property
    def success(self) -> bool:
        return self.error is None


class TableOut(BaseModel):
    name: str
    columns: list[str]
    row_count: int
    primary_keys: list[str]


class SchemaResponse(BaseModel):
    dialect: str
    tables: list[TableOut]


class ColumnDetailOut(BaseModel):
    name: str
    type: str
    nullable: bool
    is_primary_key: bool
    default: str | None = None


class ForeignKeyOut(BaseModel):
    column: str
    references_table: str
    references_column: str


class IndexOut(BaseModel):
    name: str
    columns: list[str]
    unique: bool


class TableDetailResponse(BaseModel):
    """Full "ORM-style" view of a single table: every column with its
    type/nullability/PK flag, its foreign keys as relationships, its
    indexes, and a few sample rows -- everything `DatabaseInspector`
    already collects but the plain `/schema` endpoint above discards.
    """

    name: str
    dialect: str
    columns: list[ColumnDetailOut]
    primary_keys: list[str]
    foreign_keys: list[ForeignKeyOut]
    indexes: list[IndexOut]
    row_count: int
    sample_rows: list[dict]


# --- Routes -----------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/llm/health")
def llm_health() -> dict[str, object]:
    connected, message = check_ollama_connection()
    return {
        "status": "ok" if connected else "error",
        "message": message,
        **llm_connection_info(),
    }


@app.get("/databases", response_model=DatabaseListResponse)
def list_databases() -> DatabaseListResponse:
    """Every database currently registered (Milestone 7/8): the
    original configured one plus any the user has uploaded.
    """
    return DatabaseListResponse(
        databases=[
            DatabaseOut(id=entry.id, name=entry.name, dialect=entry.dialect, is_default=entry.is_default)
            for entry in _registry.list_databases()
        ]
    )


# Upload guard: one giant file must not be able to fill the disk.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@app.post("/databases/upload", response_model=DatabaseOut)
async def upload_database(file: fastapi.UploadFile = fastapi.File(...)) -> DatabaseOut:
    """Milestone 7: let a user add their own database file.

    Native SQLite (.sqlite/.sqlite3/.db) is registered directly.
    Tabular files (.csv/.xls/.xlsx) are first converted to SQLite
    (one table per file/sheet, see database/ingestion.py) into a
    second temp file, which then flows through the exact same
    registry validation as a native upload.

    The registered file lands under data/uploads/, so /schema,
    /schema/tables, and /ask can all target it by db_id immediately.
    """
    if not file.filename:
        raise fastapi.HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".sqlite", ".sqlite3", ".db", ".csv", ".xls", ".xlsx"):
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Upload .sqlite, .db, .csv, .xls, or .xlsx.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise fastapi.HTTPException(
                status_code=413,
                detail=f"File is too large ({len(contents) // (1024 * 1024)}MB). Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.",
            )
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    converted_path: Path | None = None
    try:
        display_name = Path(file.filename).stem
        if suffix in (".csv", ".xls", ".xlsx"):
            # Tabular upload: convert to SQLite first, then register
            # exactly like a native file (same validation, same storage).
            with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as converted:
                converted_path = Path(converted.name)
            try:
                imported = ingest_tabular_upload(tmp_path, display_name, converted_path)
            except IngestionError as exc:
                raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
            _log.info(
                "databases.upload.converted",
                extra={
                    "upload_filename": file.filename,
                    "tables": ",".join(t.name for t in imported),
                },
            )
            entry = _registry.add_sqlite_upload(converted_path, display_name)
        else:
            entry = _registry.add_sqlite_upload(tmp_path, display_name)
    except InvalidDatabaseFileError as exc:
        _log.warning("databases.upload.rejected", extra={"upload_filename": file.filename, "error": str(exc)})
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
        if converted_path is not None:
            converted_path.unlink(missing_ok=True)

    _log.info("databases.upload.success", extra={"db_id": entry.id, "upload_filename": file.filename})
    return DatabaseOut(id=entry.id, name=entry.name, dialect=entry.dialect, is_default=entry.is_default)


@app.get("/schema", response_model=SchemaResponse)
def schema(db_id: str = DEFAULT_DB_ID) -> SchemaResponse:
    """Full database schema, for the sidebar in the chat UI."""
    with _tracer.start_as_current_span("api.schema") as span:
        span.set_attribute("api.db_id", db_id)
        try:
            engine = _registry.get_engine(db_id)
        except KeyError:
            raise fastapi.HTTPException(status_code=404, detail=f"Unknown database id: {db_id}") from None
        db_schema = DatabaseInspector(engine).inspect_database()
        return SchemaResponse(
            dialect=db_schema.dialect,
            tables=[
                TableOut(
                    name=table.name,
                    columns=[c.name for c in table.columns],
                    row_count=table.row_count,
                    primary_keys=table.primary_keys,
                )
                for table in db_schema.tables
            ],
        )


@app.get("/schema/tables/{table_name}", response_model=TableDetailResponse)
def table_detail(table_name: str, db_id: str = DEFAULT_DB_ID) -> TableDetailResponse:
    """Full detail for one table: columns with types/PK flags, foreign
    keys, indexes, and sample rows -- for the "click a table to see its
    schema architecture" view in the sidebar.
    """
    with _tracer.start_as_current_span("api.schema.table_detail") as span:
        span.set_attribute("api.table_name", table_name)
        span.set_attribute("api.db_id", db_id)
        try:
            engine = _registry.get_engine(db_id)
        except KeyError:
            raise fastapi.HTTPException(status_code=404, detail=f"Unknown database id: {db_id}") from None
        db_schema = DatabaseInspector(engine).inspect_database()
        table = db_schema.get_table(table_name)
        if table is None:
            _log.warning("schema.table_detail.not_found", extra={"table_name": table_name})
            raise fastapi.HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        return TableDetailResponse(
            name=table.name,
            dialect=db_schema.dialect,
            columns=[
                ColumnDetailOut(
                    name=c.name,
                    type=c.type,
                    nullable=c.nullable,
                    is_primary_key=c.is_primary_key,
                    default=c.default,
                )
                for c in table.columns
            ],
            primary_keys=table.primary_keys,
            foreign_keys=[
                ForeignKeyOut(
                    column=fk.column,
                    references_table=fk.references_table,
                    references_column=fk.references_column,
                )
                for fk in table.foreign_keys
            ],
            indexes=[
                IndexOut(name=idx.name, columns=idx.columns, unique=idx.unique)
                for idx in table.indexes
            ],
            row_count=table.row_count,
            sample_rows=table.sample_rows,
        )


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    """Run one question through the full agent pipeline.

    NOTE: intentionally a plain (non-async) `def`: the pipeline is
    fully synchronous (SQLAlchemy + blocking LLM HTTP calls), and
    FastAPI runs `def` routes in a worker threadpool. An `async def`
    here would block the single event loop for the whole ~1min call
    and stall every other request (/schema, /health, ...). Same reason
    applies to the other `def` routes in this file; only
    `upload_database` stays `async` (it awaits the file upload).

    Reuses the caller's `session_id` if provided (so follow-up
    questions resolve against Milestone 5 conversation memory), or
    mints a new one on first contact.

    Milestone 8: `database_ids` selects which registered database(s)
    to run against. A single id targets just that database (the
    common case, and the only case before this milestone). Multiple
    ids, or omitting the field entirely, fans the same question out to
    every one of them concurrently and returns one result per
    database in `per_database`, alongside a top-level result taken
    from the first database that answered successfully (so existing
    single-database callers keep working unchanged).

    Intent gate: the question is classified once here (not once per
    database). CHAT messages get a short reply without touching any
    pipeline; DATA_QUERY fans out as before, with the intent passed
    through so pipelines don't re-classify.
    """
    with _tracer.start_as_current_span("api.ask") as span:
        question = payload.question.strip()
        if not question:
            raise fastapi.HTTPException(status_code=400, detail="question must not be empty")

        session_id = payload.session_id or str(uuid.uuid4())
        span.set_attribute("api.session_id", session_id)

        db_ids = _resolve_db_ids(payload.database_ids)
        span.set_attribute("api.db_ids", ",".join(db_ids))

        conversation = _get_conversation(session_id)
        _log.info(
            "ask.start",
            extra={
                "session_id": session_id,
                "question": question,
                "db_ids": ",".join(db_ids),
                "conversation_turns": len(conversation.recent()),
            },
        )

        intent = _intent_classifier.classify(question, conversation_turns=conversation.recent())
        span.set_attribute("api.intent", intent)

        if intent == CHAT:
            reply = _chat_answerer.generate_chat_reply(
                question, conversation_turns=conversation.recent()
            )
            _log.info("ask.chat", extra={"session_id": session_id, "question": question})
            return AskResponse(
                session_id=session_id, question=question, answer=reply,
                attempts=0, linked_tables=[], intent=CHAT,
            )

        per_database: list[PerDatabaseAskResult] = []
        for db_id in db_ids:
            entry = _registry.get(db_id)
            pipeline = _get_pipeline(db_id)
            try:
                result = pipeline.ask(
                    question,
                    conversation=conversation if len(db_ids) == 1 else None,
                    intent=intent,
                    session_id=session_id,
                )
            except Exception:
                _log.exception(
                    "ask.pipeline_exception",
                    extra={"session_id": session_id, "question": question, "db_id": db_id},
                )
                per_database.append(
                    PerDatabaseAskResult(
                        database_id=db_id,
                        database_name=entry.name,
                        error="Internal error while answering this question.",
                        attempts=0,
                        linked_tables=[],
                    )
                )
                continue

            if result.success:
                _log.info(
                    "ask.success",
                    extra={
                        "session_id": session_id,
                        "db_id": db_id,
                        "question": question,
                        "sql": result.sql,
                        "attempts": result.attempts,
                        "linked_tables": ",".join(result.linked_tables),
                        "row_count": result.query_result.row_count if result.query_result else None,
                    },
                )
            else:
                _log.error(
                    "ask.failed",
                    extra={
                        "session_id": session_id,
                        "db_id": db_id,
                        "question": question,
                        "sql": result.sql,
                        "attempts": result.attempts,
                        "linked_tables": ",".join(result.linked_tables),
                        "error": result.error,
                    },
                )

            query_result_out = None
            if result.query_result is not None and result.query_result.success:
                query_result_out = QueryResultOut(
                    columns=result.query_result.columns,
                    rows=result.query_result.rows,
                    row_count=result.query_result.row_count,
                    truncated=result.query_result.truncated,
                    execution_ms=result.query_result.execution_ms,
                )

            per_database.append(
                PerDatabaseAskResult(
                    database_id=db_id,
                    database_name=entry.name,
                    sql=result.sql,
                    answer=result.answer,
                    error=result.error,
                    attempts=result.attempts,
                    linked_tables=result.linked_tables,
                    query_result=query_result_out,
                )
            )

        # Prefer the first successful database's result as the primary
        # one (so a single-database request behaves exactly as before);
        # fall back to the first result at all if every database failed.
        primary = next((r for r in per_database if r.error is None), per_database[0])

        return AskResponse(
            session_id=session_id,
            question=question,
            sql=primary.sql,
            answer=primary.answer,
            error=primary.error if len(per_database) == 1 else None,
            attempts=primary.attempts,
            linked_tables=primary.linked_tables,
            query_result=primary.query_result,
            per_database=per_database,
            intent=intent,
        )


@app.post("/sql/execute", response_model=SqlExecuteResponse)
def execute_sql(payload: SqlExecuteRequest) -> SqlExecuteResponse:
    """Run hand-written SQL from the SQL editor (no LLM involved).

    The statement goes through the exact same safety gates as
    LLM-generated SQL: sqlglot AST validation (single read-only
    SELECT) plus the executor's timeout and row cap. Anything else
    comes back as `error`, never touches the database.
    """
    db_id = payload.db_id or DEFAULT_DB_ID
    try:
        entry = _registry.get(db_id)
    except KeyError:
        raise fastapi.HTTPException(status_code=404, detail=f"Unknown database id: {db_id}") from None

    sql = (payload.sql or "").strip()
    if not sql:
        return SqlExecuteResponse(database_id=db_id, database_name=entry.name, sql="", error="SQL is empty.")

    with _tracer.start_as_current_span("api.sql.execute") as span:
        span.set_attribute("api.db_id", db_id)
        validation = SQLValidator().validate(sql)
        if not validation.valid:
            _log.warning("sql.execute.rejected", extra={"db_id": db_id, "reason": validation.reason})
            return SqlExecuteResponse(
                database_id=db_id, database_name=entry.name, sql=sql,
                error=f"Rejected: {validation.reason}",
            )
        result = QueryExecutor(entry.engine).execute(sql)
        if not result.success:
            return SqlExecuteResponse(
                database_id=db_id, database_name=entry.name, sql=sql, error=result.error,
            )
        _log.info(
            "sql.execute.success",
            extra={"db_id": db_id, "row_count": result.row_count, "execution_ms": result.execution_ms},
        )
        return SqlExecuteResponse(
            database_id=db_id, database_name=entry.name, sql=sql,
            columns=result.columns, rows=result.rows, row_count=result.row_count,
            truncated=result.truncated, execution_ms=result.execution_ms,
        )


@app.post("/cancel")
def cancel(payload: SessionRequest) -> dict[str, str]:
    """Cooperative cancel: flag the session so any in-flight ask()
    stops before its next LLM call and returns "Cancelled." instead
    of burning retries. Always use alongside aborting the HTTP fetch
    client-side -- this stops the server-side work and keeps the
    cancelled turn out of conversation memory."""
    cancel_session(payload.session_id)
    _log.info("ask.cancel", extra={"session_id": payload.session_id})
    return {"status": "cancelled"}


@app.post("/reset")
def reset(payload: SessionRequest) -> dict[str, str]:
    """Drop a session's conversation memory (the UI's "New chat" action)."""
    with _conversations_lock:
        _conversations.pop(payload.session_id, None)
    _state_store.delete_session_turns(payload.session_id)
    return {"status": "ok"}
