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

### Milestone 4 — Lightweight schema linking (not vector RAG yet)

Identify relevant tables/columns via name matching + LLM before
generation, plus few-shot exemplars and value grounding for filter
values. Vector-based retrieval (ChromaDB, originally Phases 11-12)
is deferred until a schema large enough to need it is actually in
scope — for `concert_singer`'s 4 tables it would add latency and
failure surface with no accuracy benefit.

### Milestone 5 — Conversation memory

Resolve references like "what about the previous city?" across turns.
Maps to the original Phase 10.

### Milestone 6 — Serving layer

FastAPI backend (original Phase 23) with streaming responses, plus the
React chat UI (original Phase 23b) with a SQL-inspection panel for
transparency. Streamlit (original Phase 22) stays an optional internal
debug tool, not the production surface.

## Security notes carried forward from the review

- AST validation (Milestone 1) is a **safety-critical** layer, not
  polish — string-matching alone can miss stacked statements or CTEs
  wrapping a mutation.
- Prefer opening the SQLite connection itself in read-only mode
  (`file:...?mode=ro`) as defense in depth beyond app-layer checks —
  not yet done as of Milestone 1, worth adding alongside Milestone 3.
- If row data ever flows back into a prompt (it does, in the answer
  generator), treat it as untrusted content, not instructions.
