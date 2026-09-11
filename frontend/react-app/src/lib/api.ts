// Every request goes through /api, which Vercel routes to the FastAPI
// service (backend/main.py) in every environment, and which the Vite dev
// server proxies the same way locally (see vite.config.ts). No env var or
// hardcoded host is needed anywhere in the app.
const API_BASE = "/api"

// Local Ollama answers take ~60-90s (two LLM calls per question), so the
// ask timeout is generous. Schema never touches the LLM and should be instant;
// if it times out the backend is almost certainly not running.
const SCHEMA_TIMEOUT_MS = 15_000
const ASK_TIMEOUT_MS = 300_000

export interface TableSchema {
  name: string
  columns: string[]
  row_count: number
  primary_keys: string[]
}

export interface SchemaResponse {
  dialect: string
  tables: TableSchema[]
}

export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  truncated: boolean
  execution_ms: number
}

export interface AskResponse {
  session_id: string
  question: string
  sql: string | null
  answer: string | null
  error: string | null
  attempts: number
  linked_tables: string[]
  query_result: QueryResult | null
}

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s — is the backend running?`)
    }
    throw new Error(`Cannot reach the backend (${url}) — is it running on port 8000? Run ./run.sh`)
  } finally {
    clearTimeout(timer)
  }
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail ?? response.statusText
    throw new Error(`Request failed (${response.status}): ${detail}`)
  }
  return response.json() as Promise<T>
}

export async function fetchSchema(): Promise<SchemaResponse> {
  const response = await fetchWithTimeout(`${API_BASE}/schema`, {}, SCHEMA_TIMEOUT_MS)
  return parseOrThrow<SchemaResponse>(response)
}

export async function askQuestion(question: string, sessionId: string): Promise<AskResponse> {
  const response = await fetchWithTimeout(
    `${API_BASE}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    },
    ASK_TIMEOUT_MS,
  )
  return parseOrThrow<AskResponse>(response)
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  })
}
