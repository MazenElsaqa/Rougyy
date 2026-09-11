import { useRef, useState } from "react"
import type { DatabaseInfo } from "../lib/api"

interface DatabaseSelectorProps {
  databases: DatabaseInfo[]
  /** null = "All databases" (Milestone 8's search-everything mode). */
  selectedIds: string[] | null
  onSelect: (ids: string[] | null) => void
  onUpload: (file: File) => Promise<void>
  uploading: boolean
  uploadError: string | null
}

/**
 * Milestone 7 + 8 combined: lets the user add their own SQLite
 * database file, then choose whether to run chat questions against
 * one specific database or search across every registered database
 * at once.
 */
export function DatabaseSelector({
  databases,
  selectedIds,
  onSelect,
  onUpload,
  uploading,
  uploadError,
}: DatabaseSelectorProps) {
  const [open, setOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isAll = selectedIds === null
  const label = isAll
    ? `All databases (${databases.length})`
    : databases.find((db) => db.id === selectedIds?.[0])?.name ?? "Select database"

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (file) void onUpload(file)
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12px] font-medium text-foreground hover:bg-surface-muted"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5 text-muted" aria-hidden="true">
          <ellipse cx="10" cy="5" rx="6" ry="2.2" stroke="currentColor" strokeWidth="1.4" />
          <path
            d="M4 5v5c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2V5M4 10v5c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2v-5"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
        <span className="max-w-[140px] truncate">{label}</span>
        <svg viewBox="0 0 20 20" fill="none" className="h-3 w-3 text-muted" aria-hidden="true">
          <path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-10 cursor-default"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-full z-20 mt-1.5 w-64 overflow-hidden rounded-lg border border-border bg-surface shadow-lg">
            <div className="max-h-56 overflow-y-auto p-1">
              <button
                type="button"
                onClick={() => {
                  onSelect(null)
                  setOpen(false)
                }}
                className={`flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-[13px] hover:bg-surface-muted ${
                  isAll ? "text-primary" : "text-foreground"
                }`}
              >
                <span>All databases</span>
                <span className="text-[11px] text-muted">search everything</span>
              </button>
              {databases.map((db) => (
                <button
                  key={db.id}
                  type="button"
                  onClick={() => {
                    onSelect([db.id])
                    setOpen(false)
                  }}
                  className={`flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-[13px] hover:bg-surface-muted ${
                    !isAll && selectedIds?.[0] === db.id ? "text-primary" : "text-foreground"
                  }`}
                >
                  <span className="truncate">{db.name}</span>
                  {db.is_default && <span className="text-[11px] text-muted">default</span>}
                </button>
              ))}
            </div>
            <div className="border-t border-border p-1">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-[13px] font-medium text-primary hover:bg-surface-muted disabled:opacity-60"
              >
                <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
                  <path d="M10 4v9m0-9l3.5 3.5M10 4L6.5 7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M4 14v1.5A1.5 1.5 0 005.5 17h9a1.5 1.5 0 001.5-1.5V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                {uploading ? "Uploading…" : "Add your own database"}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".sqlite,.sqlite3,.db"
                className="hidden"
                onChange={handleFileChange}
              />
              {uploadError && <p className="px-2.5 py-1 text-[11px] text-destructive">{uploadError}</p>}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
