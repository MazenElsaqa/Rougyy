import { useState } from "react"
import type { QueryResult } from "../lib/api"

interface QueryInspectorProps {
  sql: string | null
  queryResult: QueryResult | null
  attempts: number
  linkedTables: string[]
}

/**
 * The signature element of the chat UI: shows exactly what the agent
 * ran and what came back, so the natural-language answer is never the
 * only thing the user has to trust.
 */
export function QueryInspector({ sql, queryResult, attempts, linkedTables }: QueryInspectorProps) {
  const [sqlOpen, setSqlOpen] = useState(false)

  if (!sql) return null

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-border bg-surface">
      <button
        type="button"
        onClick={() => setSqlOpen((open) => !open)}
        className="flex w-full items-center justify-between px-3 py-2 text-left"
        aria-expanded={sqlOpen}
      >
        <span className="flex items-center gap-2 text-[13px] font-medium text-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
          SQL
          {attempts > 1 && (
            <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-normal text-muted">
              {attempts} attempts
            </span>
          )}
        </span>
        <svg
          viewBox="0 0 20 20"
          fill="none"
          className={`h-4 w-4 shrink-0 text-muted transition-transform ${sqlOpen ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          <path d="M5 7.5 10 12.5 15 7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {sqlOpen && (
        <div className="border-t border-border bg-surface-muted px-3 py-3">
          <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-[12.5px] leading-relaxed text-foreground">
            {sql}
          </pre>
          {linkedTables.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {linkedTables.map((table) => (
                <span
                  key={table}
                  className="rounded-full border border-border bg-surface px-2 py-0.5 font-mono text-[11px] text-muted"
                >
                  {table}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {queryResult && queryResult.row_count > 0 && (
        <div className="border-t border-border">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12.5px]">
              <thead>
                <tr className="border-b border-border bg-surface-muted">
                  {queryResult.columns.map((column) => (
                    <th key={column} className="whitespace-nowrap px-3 py-1.5 font-mono font-medium text-muted">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queryResult.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className="border-b border-border last:border-0">
                    {queryResult.columns.map((column) => (
                      <td key={column} className="whitespace-nowrap px-3 py-1.5 font-mono text-foreground">
                        {String(row[column] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-border px-3 py-1.5 text-[11px] text-muted-foreground">
            {queryResult.row_count} row{queryResult.row_count === 1 ? "" : "s"}
            {queryResult.truncated ? " (truncated)" : ""} · {queryResult.execution_ms.toFixed(1)}ms
          </div>
        </div>
      )}
    </div>
  )
}
