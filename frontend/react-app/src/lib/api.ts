// Every request goes through /api, which Vercel routes to the FastAPI
// service (backend/main.py) in every environment, and which the Vite dev
// server proxies the same way locally (see vite.config.ts). No env var or
// hardcoded host is needed anywhere in the app.
const API_BASE = "/api"

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

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail ?? response.statusText
    throw new Error(`Request failed (${response.status}): ${detail}`)
  }
  return response.json() as Promise<T>
}

export async function fetchSchema(): Promise<SchemaResponse> {
  const response = await fetch(`${API_BASE}/schema`)
  return parseOrThrow<SchemaResponse>(response)
}

export async function askQuestion(question: string, sessionId: string): Promise<AskResponse> {
  const response = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  })
  return parseOrThrow<AskResponse>(response)
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  })
}
