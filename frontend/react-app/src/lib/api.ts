// Every request goes through /api, which Vercel routes to the FastAPI
// service (backend/main.py) in every environment, and which the Vite dev
// server proxies the same way locally (see vite.config.ts). No env var or
// hardcoded host is needed anywhere in the app.
const API_BASE = "/api"

// Local Ollama answers take ~60-90s (two LLM calls per question), so the
// ask timeout is generous. Schema never touches the LLM and is normally
// instant; its 60s timeout is only a safety net (e.g. first load while
// the backend is cold-starting) -- a timeout here still means the backend
// is most likely not running.
const SCHEMA_TIMEOUT_MS = 60_000
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

export interface ColumnDetail {
  name: string
  type: string
  nullable: boolean
  is_primary_key: boolean
  default: string | null
}

export interface ForeignKeyDetail {
  column: string
  references_table: string
  references_column: string
}

export interface IndexDetail {
  name: string
  columns: string[]
  unique: boolean
}

export interface TableDetail {
  name: string
  dialect: string
  columns: ColumnDetail[]
  primary_keys: string[]
  foreign_keys: ForeignKeyDetail[]
  indexes: IndexDetail[]
  row_count: number
  sample_rows: Record<string, unknown>[]
}

export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  truncated: boolean
  execution_ms: number
}

export interface PerDatabaseAskResult {
  database_id: string
  database_name: string
  sql: string | null
  answer: string | null
  error: string | null
  attempts: number
  linked_tables: string[]
  query_result: QueryResult | null
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
  per_database: PerDatabaseAskResult[]
  /** CHAT replies skip SQL entirely; DATA_QUERY is the classic path. */
  intent: string
}

export interface DatabaseInfo {
  id: string
  name: string
  dialect: string
  is_default: boolean
}

export interface DatabaseListResponse {
  databases: DatabaseInfo[]
}

/** Milestone 8: null/undefined means "all databases at once". */
export type DatabaseSelection = string[] | null

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs: number,
  externalSignal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const onExternalAbort = () => controller.abort()
  if (externalSignal?.aborted) controller.abort()
  else externalSignal?.addEventListener("abort", onExternalAbort)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      if (!timedOut) throw error // user-cancelled: the caller reports "Cancelled."
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s — is the backend running?`)
    }
    throw new Error(`Cannot reach the backend (${url}) — is it running on port 8000? Run ./run.sh`)
  } finally {
    clearTimeout(timer)
    externalSignal?.removeEventListener("abort", onExternalAbort)
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

export async function fetchSchema(databaseId?: string): Promise<SchemaResponse> {
  const query = databaseId ? `?db_id=${encodeURIComponent(databaseId)}` : ""
  const response = await fetchWithTimeout(`${API_BASE}/schema${query}`, {}, SCHEMA_TIMEOUT_MS)
  return parseOrThrow<SchemaResponse>(response)
}

export async function askQuestion(
  question: string,
  sessionId: string,
  databaseIds?: DatabaseSelection,
  signal?: AbortSignal,
): Promise<AskResponse> {
  const response = await fetchWithTimeout(
    `${API_BASE}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId, database_ids: databaseIds ?? null }),
    },
    ASK_TIMEOUT_MS,
    signal,
  )
  return parseOrThrow<AskResponse>(response)
}

export async function fetchTableDetail(tableName: string, databaseId?: string): Promise<TableDetail> {
  const query = databaseId ? `?db_id=${encodeURIComponent(databaseId)}` : ""
  const response = await fetchWithTimeout(
    `${API_BASE}/schema/tables/${encodeURIComponent(tableName)}${query}`,
    {},
    SCHEMA_TIMEOUT_MS,
  )
  return parseOrThrow<TableDetail>(response)
}

export async function fetchDatabases(): Promise<DatabaseListResponse> {
  const response = await fetchWithTimeout(`${API_BASE}/databases`, {}, SCHEMA_TIMEOUT_MS)
  return parseOrThrow<DatabaseListResponse>(response)
}

/** Milestone 7: upload a user's own SQLite file (.sqlite/.sqlite3/.db)
 * and register it so it shows up in the database selector immediately.
 */
export async function uploadDatabase(file: File): Promise<DatabaseInfo> {
  const formData = new FormData()
  formData.append("file", file)
  const response = await fetchWithTimeout(
    `${API_BASE}/databases/upload`,
    { method: "POST", body: formData },
    SCHEMA_TIMEOUT_MS,
  )
  return parseOrThrow<DatabaseInfo>(response)
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  })
}
