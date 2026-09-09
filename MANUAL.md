# Rougyy (AI Database Agent) — User Manual

A conversational AI agent that answers natural-language questions about a
database. It never lets the LLM touch the database directly — every SQL
statement it generates is parsed, validated as a safe read-only `SELECT`,
executed, and only then turned into a grounded natural-language answer.

This manual covers what you need installed, how to set the project up, how
to run it (both the command-line tool and the web app), how to actually use
it once it's running, and how the whole thing works end to end.

---

## 1. What you need

| Requirement | Version | Used for |
|---|---|---|
| Python | 3.11+ | Core agent, CLI, FastAPI backend |
| Node.js | 18+ | React frontend (Vite) |
| pip | any recent | Installing Python dependencies |
| npm | any recent | Installing frontend dependencies |
| An LLM API key | — | SQL generation and answer generation |

The agent talks to any **OpenAI-compatible** LLM endpoint. You can use:
- **OpenAI** directly (`gpt-4o`, etc.)
- **Google Gemini**, via its OpenAI-compatible endpoint
- A **local Ollama** server (no API key needed, just a placeholder value)

You do **not** need to install a separate database server — the project
ships with a small SQLite database (`concert_singer`, from the Spider
dataset) that gets built locally by a setup script.

---

## 2. Installing the project

Run these from the project root.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt
pip install -e .

# 3. Configure environment variables
cp .env.example .env
```

Now open `.env` and set your LLM credentials. Pick ONE of these blocks:

```bash
# Option A: OpenAI
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o

# Option B: Gemini (OpenAI-compatible endpoint)
OPENAI_API_KEY=AIza...
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-1.5-pro

# Option C: Local Ollama (no real key needed)
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3
```

```bash
# 4. Build the local demo database (creates data/concert_singer.sqlite)
python scripts/setup_db.py
```

That's it — the core agent is ready. The steps below cover the two ways to
run it: a quick command-line tool, or the full web app.

---

## 3. Running it

### Option A — Command line (fastest way to try it)

```bash
# One-off question
python main.py "Which singers are from France?"

# Interactive chat (remembers earlier turns in the same session)
python main.py --chat

# Just inspect the database schema
python main.py

# Run the accuracy evaluation suite against a held-out question set
python scripts/run_eval.py
```

### Option B — Full web app (chat UI + backend API)

This runs two servers side by side: the FastAPI backend (the agent, over
HTTP) and the React frontend (the chat interface).

```bash
# Terminal 1 — backend, on port 8000
cd backend
pip install -e .
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend, on port 5173 (proxies /api to the backend)
cd frontend/react-app
npm install
npm run dev
```

Then open the URL Vite prints (typically `http://localhost:5173`) in your
browser.

> On Vercel, both services deploy together as one project automatically
> (see `vercel.json`) — there's nothing to configure by hand in production.

---

## 4. How to use it

### Using the CLI

- `python main.py "<question>"` runs one question and prints:
  - the SQL the agent generated
  - how many rows came back
  - the final natural-language answer (or an error, if something failed)
- `python main.py --chat` opens a REPL. Type a question, press Enter, get
  an answer. Follow-up questions can refer back to earlier ones in the same
  session, for example:
  ```
  > Which singers are from France?
    Answer: ...
  > What about from Canada?
    Answer: ...   (correctly reinterprets "what about" using the last turn)
  ```
  Type `exit`, `quit`, or press Ctrl-D to leave.

### Using the web app

The chat UI has three parts:

1. **Schema sidebar** (left) — every table in the database, its columns,
   and its row count. Whichever tables the agent decided were relevant to
   your latest question get highlighted here, so you can see what it's
   "looking at."
2. **Chat panel** (center) — type a question in the composer at the
   bottom and press Enter. Messages appear as a normal chat thread. A
   typing indicator shows while the agent is working.
3. **Query inspector** (right, or below on mobile) — for the most recent
   answer, shows the exact SQL that was executed (collapsible), the tables
   the agent linked to the question, and the raw returned rows as a table
   with row count and execution time. This exists so you never have to
   just "trust" the natural-language answer — you can always check the
   real data it came from.

Use **"New chat"** to clear conversation memory and start fresh (this
matters because follow-up questions rely on earlier turns — starting a new
chat prevents old context from leaking into unrelated questions).

### Example questions to try (against the bundled `concert_singer` data)

- "Which singers are from France?"
- "How many concerts were held at each stadium?"
- "What is the average capacity of stadiums with more than 3 concerts?"
- "List singers ordered by age, oldest first."
- "What about just from Canada?" (as a follow-up to a country-filtered
  question — tests conversation memory)

---

## 5. Project flow — what happens when you ask a question

```
 Your question
      │
      ▼
 1. Schema linking       → scans the full DB schema, keeps only the
                             tables relevant to your question (+ any
                             tables joined to them via foreign keys),
                             and looks up real example values for
                             filter-like columns (e.g. actual country
                             names as stored in the DB)
      │
      ▼
 2. Conversation context → if you're in a chat session, recent turns
                             are folded in so follow-ups like "what
                             about Canada?" resolve correctly
      │
      ▼
 3. SQL generation        → the LLM is given the narrowed schema, a few
                             worked examples, and your question (+ any
                             conversation history), and writes one SQL
                             SELECT statement
      │
      ▼
 4. Safety validation     → the SQL is parsed (not just string-matched)
                             and rejected if it's anything other than a
                             single, safe, read-only SELECT — no
                             INSERT/UPDATE/DELETE/DROP/ALTER/etc. can
                             ever reach the database
      │
      ▼
 5. Execution              → the validated query runs against the real
                             database, read-only, with a timeout
      │
      ▼
 6. Self-correction        → if validation or execution failed, the
     (loop back to 3)         error is fed back to the LLM and it tries
                             again (up to 3 attempts total)
      │
      ▼
 7. Answer generation      → once a query succeeds, the LLM turns the
                             actual returned rows into a plain-English
                             answer — grounded in real data, not guessed
      │
      ▼
 Your answer (+ the SQL and rows, visible in the inspector/CLI output)
```

**The core principle:** the LLM never talks to the database. It only ever
proposes SQL. The database is always the source of truth for facts; the
LLM's only jobs are writing the query and phrasing the final answer.

---

## 6. Features

- **Natural-language to SQL** — ask questions in plain English, get real
  answers backed by actual query results, not hallucinated ones.
- **Self-correcting queries** — if generated SQL is invalid or fails to
  execute, the agent automatically retries with the error fed back in,
  instead of just failing on the first mistake.
- **Schema-aware, not brute-force** — before generating SQL, the agent
  narrows down to the tables actually relevant to your question (plus
  anything joined to them), and grounds filter values (like country or
  category names) against what's really stored in the database.
- **Conversation memory** — ask a follow-up question and it resolves
  correctly against what you asked before, without repeating context
  yourself.
- **Full transparency** — every answer comes with the exact SQL that was
  run and the raw rows returned, so you can verify it rather than take the
  natural-language summary on faith.
- **Safe by construction** — SQL is validated by parsing its structure,
  not by pattern-matching text, so only single, read-only `SELECT`
  statements can ever be executed.
- **Two ways to use it** — a scriptable CLI for quick questions and
  automation, and a full chat web app for everyday use.
- **Evaluation harness** — a held-out set of question/answer pairs with an
  execution-accuracy scorer, so changes to the agent can be measured
  objectively rather than "eyeballed."

---

## 7. Project structure

```
Rougyy/
├── backend/                   # FastAPI serving layer (web API)
│   ├── main.py
│   └── pyproject.toml
├── frontend/react-app/        # React + Vite + Tailwind chat UI
├── src/ai_database_agent/
│   ├── config/                # Settings / environment loading
│   ├── database/               # Connection, schema inspection, safe execution
│   ├── observability/          # Tracing
│   ├── schema/                  # Schema linking + value grounding
│   ├── llm/                       # LLM client, SQL + answer generation
│   ├── agent/                     # The end-to-end pipeline
│   ├── memory/                    # Conversation memory
│   └── evaluation/                 # Eval dataset + scoring harness
├── tests/
├── scripts/                   # setup_db.py, run_eval.py
├── vercel.json                # Deploys backend + frontend as one project
├── main.py                    # CLI entry point
└── .env.example
```

---

## 8. Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| `OPENAI_API_KEY` errors on startup | `.env` wasn't created, or the key wasn't set — see step 3 above |
| "no such table" errors | `python scripts/setup_db.py` wasn't run yet |
| Frontend loads but questions fail | Backend isn't running, or isn't on port 8000 — check terminal 1 |
| Agent gives a wrong answer | Check the SQL in the inspector/CLI output first — the SQL, not the phrasing, is where accuracy issues actually live |
| Follow-up question ignores earlier context | Make sure you're in `--chat` mode (CLI) or haven't clicked "New chat" (web UI) — a one-off `python main.py "..."` call has no memory across separate runs |

For test coverage and internal implementation details, see `MILESTONES.md`.
