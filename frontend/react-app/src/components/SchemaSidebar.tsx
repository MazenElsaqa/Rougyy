import type { TableSchema } from "../lib/api"

interface SchemaSidebarProps {
  dialect: string | null
  tables: TableSchema[]
  linkedTables: string[]
  loading: boolean
}

export function SchemaSidebar({ dialect, tables, linkedTables, loading }: SchemaSidebarProps) {
  return (
    <aside className="flex h-full w-full flex-col border-border bg-surface md:w-64 md:border-r" aria-label="Database schema">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Schema</h2>
        {dialect && (
          <span className="rounded-full bg-surface-muted px-2 py-0.5 font-mono text-[11px] text-muted">
            {dialect}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {loading && <p className="px-2 py-2 text-sm text-muted">Loading schema…</p>}

        {!loading &&
          tables.map((table) => {
            const isLinked = linkedTables.includes(table.name)
            return (
              <div
                key={table.name}
                className={`mb-1 rounded-md px-2 py-2 transition-colors ${
                  isLinked ? "bg-primary-muted" : "hover:bg-surface-muted"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-[13px] font-medium text-foreground">
                    {table.name}
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{table.row_count} rows</span>
                </div>
                <p className="mt-0.5 truncate text-[11px] text-muted">{table.columns.join(", ")}</p>
              </div>
            )
          })}
      </div>

      <div className="border-t border-border px-4 py-3">
        <p className="text-[11px] leading-relaxed text-muted">
          Highlighted tables were selected by schema linking for the most recent question.
        </p>
      </div>
    </aside>
  )
}
