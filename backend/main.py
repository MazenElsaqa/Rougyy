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
subsequent request. It's used here as an in-memory key to a
`Conversation`. This is intentionally a plain process-local dict --
moving it to Redis/a DB is a separate concern from wiring the API up
in the first place, and is called out in MILESTONES.md as follow-up
work.

Routes are defined without the `/api` prefix (e.g. `/health`, not
`/api/health`) because Vercel strips `routePrefix` before forwarding
to this service.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from threading import Lock

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import fastapi
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_database_agent.agent.pipeline import AgentPipeline
from ai_database_agent.database.connection import get_engine
from ai_database_agent.database.inspector import DatabaseInspector
from ai_database_agent.memory.conversation import Conversation
from ai_database_agent.observability.tracing import get_tracer, setup_tracing

setup_tracing()
_tracer = get_tracer(__name__)

app = fastapi.FastAPI(title="Rougyy Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = AgentPipeline()
_conversations: dict[str, Conversation] = {}
_conversations_lock = Lock()


def _get_conversation(session_id: str) -> Conversation:
    with _conversations_lock:
        conversation = _conversations.get(session_id)
        if conversation is None:
            conversation = Conversation()
            _conversations[session_id] = conversation
        return conversation


# --- Request/response models ---------------------------------------------


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None


class SessionRequest(BaseModel):
    session_id: str


class QueryResultOut(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
    execution_ms: float


class AskResponse(BaseModel):
    session_id: str
    question: str
    sql: str | None = None
    answer: str | None = None
    error: str | None = None
    attempts: int
    linked_tables: list[str]
    query_result: QueryResultOut | None = None

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


# --- Routes -----------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/schema", response_model=SchemaResponse)
async def schema() -> SchemaResponse:
    """Full database schema, for the sidebar in the chat UI."""
    with _tracer.start_as_current_span("api.schema"):
        db_schema = DatabaseInspector(get_engine()).inspect_database()
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


@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    """Run one question through the full agent pipeline.

    Reuses the caller's `session_id` if provided (so follow-up
    questions resolve against Milestone 5 conversation memory), or
    mints a new one on first contact.
    """
    with _tracer.start_as_current_span("api.ask") as span:
        question = payload.question.strip()
        if not question:
            raise fastapi.HTTPException(status_code=400, detail="question must not be empty")

        session_id = payload.session_id or str(uuid.uuid4())
        span.set_attribute("api.session_id", session_id)

        conversation = _get_conversation(session_id)
        result = _pipeline.ask(question, conversation=conversation)

        query_result_out = None
        if result.query_result is not None and result.query_result.success:
            query_result_out = QueryResultOut(
                columns=result.query_result.columns,
                rows=result.query_result.rows,
                row_count=result.query_result.row_count,
                truncated=result.query_result.truncated,
                execution_ms=result.query_result.execution_ms,
            )

        return AskResponse(
            session_id=session_id,
            question=result.question,
            sql=result.sql,
            answer=result.answer,
            error=result.error,
            attempts=result.attempts,
            linked_tables=result.linked_tables,
            query_result=query_result_out,
        )


@app.post("/reset")
async def reset(payload: SessionRequest) -> dict[str, str]:
    """Drop a session's conversation memory (the UI's "New chat" action)."""
    with _conversations_lock:
        _conversations.pop(payload.session_id, None)
    return {"status": "ok"}
