# Rougyy — Milestone Plan

This restructures the original 40+ phase roadmap (`ai-database-agent-spec-v2.md`)
into milestones that each ship a **working, measurable, end-to-end system**,
then deepen. The original phase numbers are kept as reference points where
they map cleanly, but execution order changes: evaluation and the
end-to-end loop move much earlier, and vector-based schema RAG is deferred
until schema size actually justifies it.

## Why restructure

The original plan built every subsystem (memory, RAG, agent orchestration,
evaluation, API, frontend) to full depth in isolation before wiring them
together — the first true end-to-end demo would not have existed until
Phase 23. Two problems with that:

1. **No feedback loop.** Without an evaluation harness early, every phase
   from generation through agent orchestration would be built blind, with
   no objective signal on whether accuracy is improving.
2. **Integration risk.** Complex subsystems (retrieval, memory, agent
   planning) are much easier to get right against a working baseline than
   assembled for the first time at the end.

## Milestones

### Milestone 1 — Thin end-to-end skeleton (this one) ✅

```
question -> full schema DDL in prompt -> LLM generates SQL ->
AST validation (sqlglot) -> read-only execution -> LLM writes
a grounded answer
```

No RAG, no memory, no self-correction. Proves every layer is wired
together correctly. Maps to Phases 4 (AST validation) and 5 (LLM
integration), pulled forward and connected end to end instead of
built in isolation.

**Delivered:**
- `database/validator.py` — sqlglot AST-based SQL safety validation
  (single statement, SELECT-only, rejects INSERT/UPDATE/DELETE/DROP/
  ALTER/CREATE/PRAGMA/ATTACH by parsed node type, not string matching)
- `llm/client.py` — OpenAI-compatible client from Settings (works with
  OpenAI, Gemini's OpenAI-compatible endpoint, or a local Ollama server)
- `llm/sql_generator.py` — question + schema DDL -> SQL
- `llm/answer_generator.py` — question + SQL + executed rows -> grounded
  natural-language answer
- `agent/pipeline.py` — `AgentPipeline.ask(question)` wiring all of the
  above together, returning a structured `AgentResult`
- `scripts/setup_db.py` — builds the local `concert_singer.sqlite` demo
  database (and a separate minimal `_smoke_test.sqlite` for unit tests)
- `main.py "your question"` — CLI demo of the full pipeline

### Milestone 2 — Evaluation harness (build immediately after M1) ✅

Execution-accuracy measurement against a small held-out set of
question/SQL pairs for `concert_singer`. This becomes the regression
gate for every milestone after it — nothing here is a phase in the
original plan by number, but it corresponds to pulling Phase 18
(Evaluation) forward, right after the first working pipeline exists
instead of after 12+ more phases.

**Tracks:** execution match %, valid-SQL %, execution-success %, latency.
(Average retries will be added once Milestone 3 introduces retries.)

**Delivered:**
- `evaluation/dataset.py` — `EvalCase` model + `get_default_dataset()`,
  a 12-question held-out set for `concert_singer` covering filters,
  aggregation, `ORDER BY`/`LIMIT`, joins, `GROUP BY`, and `DISTINCT`
- `evaluation/harness.py` — `EvaluationHarness.run(dataset)` drives
  each question through the real `AgentPipeline`, executes the case's
  gold SQL separately, and scores them with `rows_match()`: an
  order- and alias-independent comparison of the two result sets
  (Spider-style execution accuracy — it's about the data returned,
  not SQL text equality)
- `EvalReport` — per-case results plus aggregate `valid_sql_rate`,
  `execution_success_rate`, `execution_accuracy`, and `avg_latency_ms`
- `scripts/run_eval.py` — CLI that runs the default dataset against
  the real pipeline and prints a per-case pass/fail breakdown plus
  the aggregate summary
- Tests stub the SQL generator with a question -> SQL map so the
  scoring logic itself (match / mismatch / invalid / missing SQL /
  aggregate averaging) is verified without needing a live LLM call

### Milestone 3 — Self-correction loop ✅

On SQL validation failure or a DB execution error, feed the error back
to the LLM with the schema and retry, capped at 2-3 attempts. Maps to
the original Phases 6-9 (query generation & correction), which were
under-specified in the original plan — this is the single highest-ROI
accuracy feature and should not wait behind memory or retrieval.

**Delivered:**
- `llm/prompts.py` — `CORRECTION_USER_TEMPLATE`, the feedback message
  that carries the DB/validation error back to the LLM
- `llm/sql_generator.py` — `CorrectionAttempt` (prior `sql` + `error`)
  and `SQLGenerator.generate(..., attempts=...)`, which replays each
  prior attempt as an `assistant` (its SQL) / `user` (the error) turn
  pair so the model sees exactly what it tried and why it failed
- `agent/pipeline.py` — `AgentPipeline.ask()` now loops up to
  `max_attempts` (default 3): validation failures and execution
  errors are appended to an in-memory attempt history and fed back
  into the next `generate()` call; the loop stops as soon as a valid,
  successfully executed query is found. `AgentResult.attempts` reports
  how many tries were used, so the evaluation harness can track average
  retries alongside accuracy
- Tests cover: happy path uses exactly 1 attempt, unsafe SQL is
  retried and still rejected after exhausting attempts, execution
  errors exhaust retries and surface the last error, and — the key
  new behavior — a wrong-table-name SQL on attempt 1 is corrected and
  succeeds on attempt 2, with the failure message visibly passed back
  into the next `generate()` call

**Not yet done (carried into later milestones):** the evaluation
harness does not yet report `avg_retries` in `EvalReport` — add this
when Milestone 4 or later revisits the harness, since it's now a
meaningful signal.

### Milestone 4 — Lightweight schema linking (not vector RAG yet) ✅

Identify relevant tables/columns via name matching before generation,
plus few-shot exemplars and value grounding for filter values.
Vector-based retrieval (ChromaDB, originally Phases 11-12) is
deferred until a schema large enough to need it is actually in
scope — for `concert_singer`'s 4 tables it would add latency and
failure surface with no accuracy benefit.

**Delivered:**
- `schema/linker.py` — `SchemaLinker`:
  - `.link(question, schema)` scores each table by token overlap
    between the question and the table's name/columns, keeps tables
    with a nonzero score, then expands that set via foreign-key
    closure (either direction) so join partners aren't dropped just
    because their own name has no lexical overlap with the question
    (e.g. "singers" + "concerts" still pulls in `singer_in_concert`).
    Falls back to the full schema if fewer than `min_tables` (default
    2) score above zero, since a no-overlap question is safer
    answered with full context than a narrow wrong guess.
  - `.value_hints(schema)` returns real distinct values for small
    categorical TEXT columns (<= 8 distinct values, each <= 40 chars)
    by querying the live database, so the LLM can match a question's
    wording to the value as actually stored (e.g. "USA" vs "United
    States") instead of guessing. Columns that look like free text are
    skipped automatically.
- `schema/formatter.py` — `SchemaFormatter.to_ddl_with_value_hints()`
  appends a `-- Known distinct values for categorical columns:` block
  to the DDL when hints are available.
- `llm/exemplars.py` — `SQLExemplar` + `get_default_exemplars()`, four
  curated (question, SQL) pairs (aggregation, ordering, join +
  group-by, distinct) deliberately different from the Milestone 2
  eval dataset so exemplars don't leak the harness's own answers.
- `llm/sql_generator.py` — `SQLGenerator.generate(..., exemplars=...)`
  replays each exemplar as a `user`/`assistant` turn pair before the
  real question, so the model sees the expected output style through
  worked examples.
- `agent/pipeline.py` — `AgentPipeline.ask()` now: builds the full
  schema once (cached), links it down to the question's relevant
  tables on every call (schemas can differ per question in the same
  pipeline instance), computes value hints for just the linked
  tables, and passes both the narrowed DDL and the default exemplars
  into every `generate()` attempt (including retries). `AgentResult`
  gained `linked_tables` so the evaluation harness and debugging tools
  can see which tables were selected for a given question.
- Tests cover: exemplars are prepended as conversation turns before
  the question (and omitted entirely when none are given), plus all
  existing pipeline/generator tests updated for the new `exemplars`
  parameter.

**Not yet done:** schema linking is not yet reported per-case in
`EvalReport` (e.g. did narrowing ever drop a table the gold SQL
needed?) — worth adding if accuracy regressions ever trace back to
linking rather than generation.

### Milestone 5 — Conversation memory ✅

Resolve references like "what about the previous city?" across turns.
Maps to the original Phase 10.

**Delivered:**
- `memory/conversation.py` — `ConversationTurn` (question + sql +
  answer) and `Conversation`: a bounded window (default: last 5
  turns) of recent turns, with `.add_turn()`, `.recent()` (returns a
  copy, not a live reference), and `.context_text()` (the turns'
  questions joined, used for schema linking). Intentionally a thin
  window rather than a full transcript or a summarization step —
  those are meaningful upgrades but not needed to prove
  reference-resolution end to end, and an unbounded transcript would
  grow every prompt indefinitely.
- `llm/sql_generator.py` — `SQLGenerator.generate(...,
  conversation_turns=...)` replays each prior turn as a
  `user`/`assistant` pair, using the same replay pattern already
  used for exemplars and self-correction attempts. Message order is:
  system -> exemplars -> conversation turns -> real question ->
  correction attempts, so the most model-relevant, most-recent
  context (the actual retry feedback for *this* question) stays
  closest to the question being asked.
- `agent/pipeline.py` — `AgentPipeline.ask(question, conversation=...)`
  is now optional-memory-aware end to end:
  - Schema linking scores against the *combined* text of recent
    turns' questions plus the current question, not the current
    question alone — so a short follow-up like "what about from
    Canada?" that shares no words with `singer`/`stadium`/etc. still
    pulls in the tables the conversation has actually been about.
  - Every generation attempt (including retries) receives the
    conversation's recent turns via `conversation_turns=`.
  - On a successful answer, the turn is appended in place to the
    same `Conversation` the caller passed in — no failed turn is
    ever recorded, so a bad attempt can't poison future turns.
  - Callers that don't pass a `Conversation` get identical behavior
    to before Milestone 5 (no conversation turns sent, linking uses
    only the current question).
- `main.py --chat` — an interactive REPL that keeps one
  `Conversation` for the whole session, so follow-up questions can
  be tried by hand end to end.
- Tests cover: `Conversation`'s window/eviction/copy-not-reference
  behavior in isolation, `SQLGenerator` replaying conversation turns
  (alone, and combined with exemplars + attempts, verifying message
  ordering), and the pipeline appending successful turns, replaying
  them into the next `ask()` call, and never recording a failed turn.

### Milestone 6 — Serving layer ✅

FastAPI backend (original Phase 23) with streaming responses, plus the
React chat UI (original Phase 23b) with a SQL-inspection panel for
transparency. Streamlit (original Phase 22) stays an optional internal
debug tool, not the production surface.

**Delivered:**
- `backend/main.py` — FastAPI service wrapping `AgentPipeline` end to
  end (Milestones 1-5 unchanged): `GET /health`, `GET /schema` (full
  DB schema for the sidebar), `POST /ask` (runs one question through
  the pipeline, keyed by a client-supplied `session_id` so follow-ups
  resolve against Milestone 5 conversation memory), `POST /reset`
  (drops a session's `Conversation`, backing the UI's "New chat").
  Session -> `Conversation` state is an in-memory, process-local dict
  guarded by a lock — sufficient to prove the serving layer end to
  end; moving it to shared storage (Redis/DB) is a separate concern
  called out below, not deferred silently.
  Routes are defined without the `/api` prefix per the Python
  services convention — Vercel's `routePrefix` strips it before
  forwarding.
- `backend/pyproject.toml` — this service's own isolated dependency
  set (it does not depend on the root project's editable install;
  `main.py` reaches `ai_database_agent` by adding the repo's `src/`
  to `sys.path`).
- `frontend/react-app/` — Vite + React 19 + TypeScript + Tailwind v4
  chat UI:
  - `SchemaSidebar` — lists tables/columns/row counts, highlighting
    whichever tables Milestone 4's linker selected for the latest
    question.
  - `ChatMessage` + `Composer` — the conversation surface itself,
    Enter-to-send (IME/Safari-composition safe), a typing indicator
    while a question is in flight.
  - `QueryInspector` — the SQL actually run (collapsible), the linked
    tables as chips, and the returned rows as a table with row
    count/timing/truncation — so the natural-language answer is never
    the only thing a user has to trust.
  - `lib/api.ts` — typed fetch wrappers for `/schema`, `/ask`,
    `/reset`, all going through `/api/*` (routed to the backend
    service in every environment; proxied identically by Vite in
    dev — no hardcoded host anywhere in the app).
  - A session id is minted client-side on load and threaded through
    every `/ask` call; "New chat" calls `/reset` and mints a new one.
- `vercel.json` — `experimentalServices` wiring both services
  (`backend` at `/api`, `frontend` at `/`) so this deploys as one
  Vercel project.

**Not yet done (explicit follow-ups, not silent gaps):**
- Session/conversation state is in-process memory, not shared
  storage — fine for a single instance, will not survive multiple
  server instances or a restart. Move to Redis or the primary DB if
  this needs to run at more than one replica.
- `/ask` is a single request/response, not a stream — the original
  plan called for `sse-starlette` streaming. The pipeline currently
  returns one `AgentResult` at the end of the retry loop rather than
  incrementally, so streaming would require restructuring
  `AgentPipeline.ask()` to yield intermediate state (attempt N
  started, SQL generated, executing, answering) — worth doing once
  the UI needs perceived latency improvements on slower models.
- No auth/rate limiting on the API — fine for local/demo use, not
  for a publicly deployed instance.

## Security notes carried forward from the review

- AST validation (Milestone 1) is a **safety-critical** layer, not
  polish — string-matching alone can miss stacked statements or CTEs
  wrapping a mutation.
- Prefer opening the SQLite connection itself in read-only mode
  (`file:...?mode=ro`) as defense in depth beyond app-layer checks —
  not yet done as of Milestone 1, worth adding alongside Milestone 3.
- If row data ever flows back into a prompt (it does, in the answer
  generator), treat it as untrusted content, not instructions.
