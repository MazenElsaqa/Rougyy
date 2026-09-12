import { useEffect, useRef, useState, type KeyboardEvent } from "react"
import { executeSql, type SqlExecuteResponse } from "../lib/api"
import { QueryInspector } from "./QueryInspector"

interface SqlEditorProps {
  /** Currently selected database (the editor's implicit `USE ...`). */
  databaseId?: string
  databaseName: string
  /** First table of that database, for the default `SELECT * ... LIMIT 5`. */
  defaultTable: string | null
}

function defaultQuery(table: string | null): string {
  return table ? `SELECT * FROM ${table} LIMIT 5` : "SELECT 1"
}

/**
 * Hand-written SQL playground: the user writes the query themselves,
 * it runs through the same read-only validation as generated SQL.
 * Opens prefilled with `SELECT * FROM <first table> LIMIT 5` against
 * whichever database is currently selected.
 */
export function SqlEditor({ databaseId, databaseName, defaultTable }: SqlEditorProps) {
  const [sql, setSql] = useState(() => defaultQuery(defaultTable))
  const [result, setResult] = useState<SqlExecuteResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [clientError, setClientError] = useState<string | null>(null)
  const lastPreset = useRef<string | null>(null)

  // Refresh the default the first time a *different* database's table
  // arrives, but never clobber what the user already typed.
  useEffect(() => {
    if (defaultTable && defaultTable !== lastPreset.current && sql.trim() === "") {
      lastPreset.current = defaultTable
      setSql(defaultQuery(defaultTable))
    }
  }, [defaultTable, sql])

  async function run() {
    const statement = sql.trim()
    if (!statement || running) return
    setRunning(true)
    setClientError(null)
    try {
      setResult(await executeSql(statement, databaseId))
    } catch (error) {
      setClientError(error instanceof Error ? error.message : String(error))
    } finally {
      setRunning(false)
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault()
      void run()
    }
  }

  return (
    <div className="flex flex-col gap-2 p-1">
      <div className="flex items-center gap-2 px-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">on</span>
        <span className="truncate rounded-full bg-primary-muted px-2 py-0.5 font-mono text-[11px] font-medium text-primary">
          {databaseName}
        </span>
      </div>
      <textarea
        value={sql}
        onChange={(event) => setSql(event.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        rows={4}
        aria-label="SQL query"
        placeholder="SELECT * FROM singer LIMIT 5"
        className="max-h-48 min-h-[96px] w-full resize-y overflow-y-auto rounded-xl border border-border bg-background px-3 py-2.5 font-mono text-[12.5px] leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void run()}
          disabled={running || !sql.trim()}
          className="flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-[12.5px] font-medium text-primary-foreground shadow-md shadow-primary/30 transition-all hover:brightness-110 disabled:opacity-40"
        >
          {running ? "Running…" : "Run"}
        </button>
        <span className="text-[11px] text-muted-foreground">⌘/Ctrl + Enter</span>
      </div>

      {clientError && (
        <div className="rounded-xl border border-destructive/20 bg-destructive-muted px-3 py-2 text-[12.5px] text-destructive">
          {clientError}
        </div>
      )}

      {result && !clientError && (
        <div>
          {result.error ? (
            <div className="rounded-xl border border-destructive/20 bg-destructive-muted px-3 py-2 text-[12.5px] text-destructive">
              {result.error}
            </div>
          ) : (
            <QueryInspector
              sql={result.sql}
              queryResult={{
                columns: result.columns,
                rows: result.rows,
                row_count: result.row_count,
                truncated: result.truncated,
                execution_ms: result.execution_ms,
              }}
              attempts={1}
              linkedTables={[]}
            />
          )}
        </div>
      )}
    </div>
  )
}
