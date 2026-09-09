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

This project was originally scoped as 40+ granular phases per
`ai-database-agent-spec-v2.md`. It is now being built as a series of
**milestones**, each of which ships a working, measurable end-to-end
system before adding sophistication — see `MILESTONES.md` for the
restructured plan and how it maps back to the original phase numbers.

## Core principle

RAG provides context about the database. **The database provides the
factual answer.** The LLM never touches the database directly —
every generated SQL statement passes through validation before
execution, and execution is read-only.

## Status

- [x] Phase 0 — Repository and environment
- [x] Phase 1 — Database foundation + tracing setup
- [x] Phase 2 — Schema representation
- [x] Phase 3 — Safe query execution
- [x] **Milestone 1 — Thin end-to-end skeleton** (question -> LLM
      generates SQL -> AST validation -> read-only execution ->
      grounded answer). Folds in Phase 4 (AST validation) and
      Phase 5 (LLM integration).
- [ ] Milestone 2 — Evaluation harness
- [ ] Milestone 3 — Self-correction loop
- [ ] Milestone 4 — Lightweight schema linking
- [ ] Milestone 5 — Conversation memory
- [ ] Milestone 6 — FastAPI backend + React frontend

See `MILESTONES.md` for details on each milestone.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
# edit .env: set OPENAI_API_KEY (and OPENAI_BASE_URL/LLM_MODEL if not
# using OpenAI directly — e.g. Gemini's OpenAI-compatible endpoint)

# builds data/concert_singer.sqlite and data/_smoke_test.sqlite locally
# (both are gitignored — regenerate any time)
python scripts/setup_db.py
```

## Running

```bash
# Phase 1 demo: inspect the schema and print a summary
python main.py

# Milestone 1 demo: ask a real question end to end
python main.py "Which singers are from France?"
python main.py "How many concerts were held at each stadium?"
```

Schema inspection prints OpenTelemetry trace spans to the console for
every step (Phase 1 tracing bootstrap). The question mode additionally
prints the LLM-generated SQL, the row count returned, and the final
grounded answer — or a clear error if generation, validation, or
execution failed at any stage.

## Environment variables

See `.env.example`. Key ones so far:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string to the SQLite database |
| `QUERY_TIMEOUT_MS` | Hard timeout for query execution (Phase 3) |
| `OTEL_SERVICE_NAME` | Service name attached to trace spans |
| `OTEL_TRACES_EXPORTER` | `console` (default) or `otlp` |
| `OPENAI_API_KEY` | API key for the configured OpenAI-compatible provider (Milestone 1) |
| `OPENAI_BASE_URL` | Override to point at a non-OpenAI provider (e.g. Gemini's OpenAI-compatible endpoint, or a local Ollama server) |
| `LLM_MODEL` | Model name passed to the provider (Milestone 1) |

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
│   ├── retrieval/                # Schema linking + RAG (Milestone 4+)
│   ├── llm/                       # LLM client, SQL + answer generation (Milestone 1+)
│   ├── agent/                     # Pipeline / orchestration (Milestone 1+)
│   ├── memory/                    # Conversation memory (Phase 10+)
│   ├── evaluation/                 # Evaluation + ablation experiments (Phase 18+)
│   └── api/                         # FastAPI backend (Phase 23+)
├── tests/
├── scripts/
└── main.py
```
