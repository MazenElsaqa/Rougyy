import { useMemo, useState } from "react"
import type { TableSchema } from "../lib/api"
import { TableDetailModal } from "./TableDetailModal"

interface SchemaSidebarProps {
  dialect: string | null
  tables: TableSchema[]
  linkedTables: string[]
  loading: boolean
  error?: string | null
  onRetry?: () => void
  databaseId?: string
}

export function SchemaSidebar({
  dialect,
  tables,
  linkedTables,
  loading,
  error,
  onRetry,
  databaseId,
}: SchemaSidebarProps) {
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [filter, setFilter] = useState("")

  const visibleTables = useMemo(() => {
    const query = filter.trim().toLowerCase()
    if (!query) return tables
    return tables.filter(
      (table) =>
        table.name.toLowerCase().includes(query) ||
        table.columns.some((column) => column.toLowerCase().includes(query)),
    )
  }, [tables, filter])

  return (
    <div className="flex h-full flex-col" aria-label="Database schema">
      <div className="flex items-center justify-between px-4 pb-2 pt-1">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted">Schema</h2>
        {dialect && (
          <span className="rounded-full border border-border bg-surface px-2 py-0.5 font-mono text-[10px] text-muted">
            {dialect}
          </span>
        )}
      </div>

      {tables.length > 4 && (
        <div className="px-3 pb-2">
          <input
            type="search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter tables…"
            aria-label="Filter tables"
            className="w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[12px] text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
          />
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {loading && (
          <div className="flex flex-col gap-1.5 px-1 py-1" aria-label="Loading schema">
            {[0, 1, 2].map((i) => (
              <div key={i} className="animate-pulse rounded-xl border border-border bg-surface px-3 py-2.5">
                <div className="h-3 w-2/3 rounded bg-surface-muted" />
                <div className="mt-1.5 h-2.5 w-1/2 rounded bg-surface-muted" />
              </div>
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="mx-1 rounded-xl border border-destructive/20 bg-destructive-muted px-3 py-2.5">
            <p className="text-[13px] font-medium text-destructive">Backend not reachable</p>
            <p className="mt-1 text-[12px] leading-relaxed text-muted">{error}</p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="mt-2 rounded-md border border-border bg-surface px-2.5 py-1 text-[12px] font-medium text-foreground hover:bg-surface-muted"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {!loading && !error && visibleTables.length === 0 && (
          <p className="px-3 py-2 text-[12px] text-muted">
            {tables.length === 0 ? "No tables in this database." : `No tables match "${filter}".`}
          </p>
        )}

        {!loading &&
          visibleTables.map((table) => {
            const isLinked = linkedTables.includes(table.name)
            return (
              <button
                key={table.name}
                type="button"
                onClick={() => setSelectedTable(table.name)}
                aria-haspopup="dialog"
                className={`group mb-1.5 w-full rounded-xl border px-3 py-2 text-left transition-all ${
                  isLinked
                    ? "border-primary/40 bg-primary-muted shadow-sm"
                    : "border-border bg-surface hover:border-muted-foreground/40 hover:shadow-sm"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5">
                    {isLinked && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />}
                    <span className="truncate font-mono text-[13px] font-semibold text-foreground">
                      {table.name}
                    </span>
                  </span>
                  <span className="shrink-0 rounded-full bg-surface-muted px-1.5 py-0.5 text-[10px] font-medium text-muted">
                    {table.row_count} rows
                  </span>
                </div>
                <p className="mt-1 truncate text-[11px] text-muted">
                  {table.columns.length} cols · {table.columns.slice(0, 4).join(", ")}
                  {table.columns.length > 4 ? "…" : ""}
                </p>
              </button>
            )
          })}
      </div>

      {selectedTable && (
        <TableDetailModal
          tableName={selectedTable}
          databaseId={databaseId}
          onClose={() => setSelectedTable(null)}
        />
      )}
    </div>
  )
}
