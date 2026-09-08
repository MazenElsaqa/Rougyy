# AI Database Agent

A production-oriented conversational AI agent that talks to a
database in natural language, with memory, hierarchical schema-aware
RAG, validated and self-correcting SQL generation, and grounded
natural-language answers.

- **Database**: SQLite (`concert_singer`, from the Spider dataset)
- **LLM**: Google Gemini API
- **Backend**: FastAPI (added in Phase 23)
- **Frontend**: React (added in Phase 23b) — Streamlit is kept as an
  internal dev/debug tool only

This project is built **incrementally, one phase at a time**, per
`ai-database-agent-spec-v2.md`. Each phase is implemented, tested,
and demoed before moving to the next.

## Core principle

RAG provides context about the database. **The database provides the
factual answer.** The LLM never touches the database directly —
every generated SQL statement passes through validation before
execution, and execution is read-only.

## Status

- [x] Phase 0 — Repository and environment
- [x] Phase 1 — Database foundation + tracing setup
- [ ] Phase 2 — Schema representation
- [ ] Phase 3 — Safe query execution
- ... (see the spec for the full phase list)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
# edit .env: set DATABASE_URL to point at your concert_singer.sqlite
```

## Running

```bash
python main.py
```

This connects to the configured database, inspects its schema, and
prints a summary — with OpenTelemetry trace spans printed to the
console for every step (Phase 1 tracing bootstrap).

## Environment variables

See `.env.example`. Key ones so far:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string to the SQLite database |
| `QUERY_TIMEOUT_MS` | Hard timeout for query execution (used from Phase 3) |
| `OTEL_SERVICE_NAME` | Service name attached to trace spans |
| `OTEL_TRACES_EXPORTER` | `console` (default) or `otlp` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Used starting Phase 5 |

## Testing

```bash
pytest tests/ -v
```

## Project structure

```
ai-database-agent/
├── frontend/react-app/        # React UI (Phase 23b)
├── src/ai_database_agent/
│   ├── config/                # Settings (Phase 1)
│   ├── database/               # Connection, inspector, schema models (Phase 1)
│   ├── observability/          # Tracing bootstrap (Phase 1)
│   ├── schema/                  # Schema representation for RAG (Phase 2+)
│   ├── retrieval/                # RAG, hierarchical retrieval, schema linker (Phase 11+)
│   ├── llm/                       # Gemini integration (Phase 5+)
│   ├── agent/                     # Query planning, orchestration (Phase 13+)
│   ├── memory/                    # Conversation memory (Phase 10+)
│   ├── evaluation/                 # Evaluation + ablation experiments (Phase 18+)
│   └── api/                         # FastAPI backend (Phase 23+)
├── tests/
├── scripts/
└── main.py
```
