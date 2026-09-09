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
- [x] **Milestone 2 — Evaluation harness** (12-question held-out set
      for `concert_singer`, scored by Spider-style execution
      accuracy — comparing returned rows, not SQL text). Pulls
      Phase 18 (Evaluation) forward as the regression gate for every
      milestone after it.
- [x] **Milestone 3 — Self-correction loop** (SQL validation/execution
      errors are fed back to the LLM and retried, capped at 3 attempts
      by default). Pulls Phases 6-9 (query generation & correction)
      forward as the highest-ROI accuracy feature.
- [x] **Milestone 4 — Lightweight schema linking** (keyword/FK-closure
      table selection + categorical value grounding + few-shot
      exemplars, no vector store). Pulls the useful part of Phases
      11-12 forward while deferring ChromaDB until schema size
      justifies it.
- [x] **Milestone 5 — Conversation memory** (a bounded window of
      recent turns is folded into schema linking and replayed into
      every generation attempt, so follow-ups like "what about from
      Canada?" resolve against the previous turn). Maps to the
      original Phase 10.
- [x] **Milestone 6 — Serving layer** (FastAPI backend exposing the
      pipeline over HTTP with per-session conversation memory, plus a
      React + Vite + Tailwind chat UI with a schema sidebar and a SQL
      / results inspector). Maps to the original Phases 23 and 23b.

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
# (Milestone 3: retries up to 3 times if validation/execution fails)
# (Milestone 4: schema is linked to relevant tables + few-shot exemplars
#  + categorical value hints before every generation attempt)
python main.py "Which singers are from France?"
python main.py "How many concerts were held at each stadium?"

# Milestone 5: interactive chat mode with conversation memory across turns
# e.g. ask "Which singers are from France?" then follow up with
# "What about from Canada?" and it resolves against the prior turn
python main.py --chat

# Milestone 2: run the evaluation harness against the held-out set
python scripts/run_eval.py
```

### Milestone 6 — web UI

```bash
# terminal 1: FastAPI backend
cd backend
pip install -e .
uvicorn main:app --reload --port 8000

# terminal 2: React frontend (proxies /api to the backend above)
cd frontend/react-app
npm install
npm run dev
```

On Vercel, `vercel.json`'s `experimentalServices` wires both up as one
project (`backend` at `/api`, `frontend` at `/`) — no separate deploy
step or hardcoded host needed in the frontend code.

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
├── backend/                   # FastAPI serving layer (Milestone 6, original Phase 23)
│   ├── main.py
│   └── pyproject.toml
├── frontend/react-app/        # React + Vite + Tailwind chat UI (Milestone 6, original Phase 23b)
├── src/ai_database_agent/
│   ├── config/                # Settings (Phase 1)
│   ├── database/               # Connection, inspector, schema models (Phase 1)
│   ├── observability/          # Tracing bootstrap (Phase 1)
│   ├── schema/                  # Schema representation + linking (Phase 2+, Milestone 4)
│   ├── llm/                       # LLM client, SQL + answer generation (Milestone 1+)
│   ├── agent/                     # Pipeline / orchestration (Milestone 1+)
│   ├── memory/                    # Conversation memory (Milestone 5, original Phase 10)
│   └── evaluation/                 # Eval dataset + harness (Milestone 2+, pulls Phase 18 forward)
├── tests/
├── scripts/
├── vercel.json                # experimentalServices wiring backend + frontend
└── main.py
```
