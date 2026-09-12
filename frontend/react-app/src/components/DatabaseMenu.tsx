import { useRef } from "react"
import type { DatabaseInfo } from "../lib/api"

interface DatabaseMenuProps {
  databases: DatabaseInfo[]
  /** null = "All databases" (search-everything mode). */
  selectedIds: string[] | null
  onSelect: (ids: string[] | null) => void
  onUpload: (file: File) => Promise<void>
  uploading: boolean
  uploadError: string | null
}

/** Inline database picker for the header dropdown (replaces the old sidebar selector). */
export function DatabaseMenu({
  databases,
  selectedIds,
  onSelect,
  onUpload,
  uploading,
  uploadError,
}: DatabaseMenuProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const isAll = selectedIds === null

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (file) void onUpload(file)
  }

  return (
    <div>
      <p className="px-2 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
        Database
      </p>
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-[13px] transition-colors hover:bg-black/5 dark:hover:bg-white/10 ${
          isAll ? "font-semibold text-primary" : "text-foreground"
        }`}
      >
        <span>All databases</span>
        <span className="text-[11px] text-muted">search everything</span>
      </button>
      {databases.map((db) => {
        const selected = !isAll && selectedIds?.[0] === db.id
        return (
          <button
            key={db.id}
            type="button"
            onClick={() => onSelect([db.id])}
            className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-[13px] transition-colors hover:bg-black/5 dark:hover:bg-white/10 ${
              selected ? "font-semibold text-primary" : "text-foreground"
            }`}
          >
            <span className="truncate">{db.name}</span>
            <span className="flex shrink-0 items-center gap-1.5 text-[11px] text-muted">
              {selected && <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />}
              {db.is_default ? "default" : db.dialect}
            </span>
          </button>
        )
      })}
      <div className="mt-1 border-t border-border/60 pt-1">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-[13px] font-medium text-primary transition-colors hover:bg-primary-muted disabled:opacity-60"
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
          accept=".sqlite,.sqlite3,.db,.csv,.xls,.xlsx"
          className="hidden"
          onChange={handleFileChange}
        />
        {uploadError && <p className="px-3 py-1 text-[11px] text-destructive">{uploadError}</p>}
      </div>
    </div>
  )
}
