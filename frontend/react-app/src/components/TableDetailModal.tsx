import { useEffect, useState } from "react"
import { fetchTableDetail, type TableDetail } from "../lib/api"

interface TableDetailModalProps {
  tableName: string
  onClose: () => void
}

/**
 * Milestone 10: clicking a table in the schema sidebar opens this
 * panel with its full "ORM-style" shape -- every column with its
 * type/nullability/PK flag, its foreign keys as relationships to
 * other tables, its indexes, and a few real sample rows.
 */
export function TableDetailModal({ tableName, onClose }: TableDetailModalProps) {
  const [detail, setDetail] = useState<TableDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchTableDetail(tableName)
      .then((result) => {
        if (!cancelled) setDetail(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tableName])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`${tableName} table schema`}
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="font-mono text-sm font-semibold text-foreground">{tableName}</h2>
            {detail && (
              <p className="text-[11px] text-muted">
                {detail.dialect} · {detail.row_count} rows
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-muted hover:bg-surface-muted"
            aria-label="Close"
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
              <path
                d="M5 5l10 10M15 5L5 15"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {loading && <p className="text-sm text-muted">Loading table schema…</p>}

          {!loading && error && (
            <div className="rounded-md border border-destructive/20 bg-destructive-muted px-3 py-2.5">
              <p className="text-[13px] font-medium text-destructive">Could not load table detail</p>
              <p className="mt-1 text-[12px] leading-relaxed text-muted">{error}</p>
            </div>
          )}

          {!loading && detail && (
            <div className="flex flex-col gap-5">
              <section>
                <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  Columns
                </h3>
                <div className="overflow-hidden rounded-md border border-border">
                  <table className="w-full text-left text-[12px]">
                    <thead className="bg-surface-muted text-muted">
                      <tr>
                        <th className="px-2.5 py-1.5 font-medium">Name</th>
                        <th className="px-2.5 py-1.5 font-medium">Type</th>
                        <th className="px-2.5 py-1.5 font-medium">Nullable</th>
                        <th className="px-2.5 py-1.5 font-medium">Key</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.columns.map((column) => (
                        <tr key={column.name} className="border-t border-border">
                          <td className="px-2.5 py-1.5 font-mono text-foreground">{column.name}</td>
                          <td className="px-2.5 py-1.5 font-mono text-muted">{column.type}</td>
                          <td className="px-2.5 py-1.5 text-muted">{column.nullable ? "yes" : "no"}</td>
                          <td className="px-2.5 py-1.5">
                            {column.is_primary_key && (
                              <span className="rounded-full bg-primary-muted px-1.5 py-0.5 text-[10px] font-medium text-primary">
                                PK
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section>
                <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  Relationships
                </h3>
                {detail.foreign_keys.length === 0 ? (
                  <p className="text-[12px] text-muted">No foreign keys on this table.</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {detail.foreign_keys.map((fk) => (
                      <li
                        key={`${fk.column}-${fk.references_table}`}
                        className="flex items-center gap-1.5 font-mono text-[12px] text-foreground"
                      >
                        <span>{fk.column}</span>
                        <span className="text-muted">→</span>
                        <span>
                          {fk.references_table}.{fk.references_column}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {detail.indexes.length > 0 && (
                <section>
                  <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Indexes
                  </h3>
                  <ul className="flex flex-col gap-1">
                    {detail.indexes.map((idx) => (
                      <li key={idx.name} className="font-mono text-[12px] text-foreground">
                        {idx.name} ({idx.columns.join(", ")}){idx.unique ? " · unique" : ""}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {detail.sample_rows.length > 0 && (
                <section>
                  <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Sample rows
                  </h3>
                  <div className="overflow-x-auto rounded-md border border-border">
                    <table className="w-full text-left text-[12px]">
                      <thead className="bg-surface-muted text-muted">
                        <tr>
                          {Object.keys(detail.sample_rows[0]).map((key) => (
                            <th key={key} className="whitespace-nowrap px-2.5 py-1.5 font-medium">
                              {key}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {detail.sample_rows.map((row, index) => (
                          <tr key={index} className="border-t border-border">
                            {Object.values(row).map((value, cellIndex) => (
                              <td
                                key={cellIndex}
                                className="whitespace-nowrap px-2.5 py-1.5 font-mono text-foreground"
                              >
                                {value === null ? <span className="text-muted">null</span> : String(value)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
