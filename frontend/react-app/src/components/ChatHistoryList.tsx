import { timeAgo, type ChatSession } from "../lib/chatHistory"

interface ChatHistoryListProps {
  sessions: ChatSession[]
  activeId: string
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

export function ChatHistoryList({ sessions, activeId, onSelect, onDelete }: ChatHistoryListProps) {
  if (sessions.length === 0) {
    return <p className="px-3 py-2 text-[12px] leading-relaxed text-muted">No conversations yet. Ask something to start one.</p>
  }

  return (
    <ul className="flex flex-col gap-0.5 px-2 py-1">
      {sessions.map((session) => {
        const isActive = session.id === activeId
        return (
          <li key={session.id}>
            <div
              className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 transition-colors ${
                isActive ? "bg-primary-muted" : "hover:bg-surface-muted"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(session.id)}
                className="min-w-0 flex-1 text-left"
                aria-current={isActive}
              >
                <p className={`truncate text-[13px] font-medium ${isActive ? "text-foreground" : "text-foreground/90"}`}>
                  {session.title}
                </p>
                <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted">
                  <span>{timeAgo(session.updatedAt)}</span>
                  <span aria-hidden="true">·</span>
                  <span>
                    {session.entries.length} msg{session.entries.length === 1 ? "" : "s"}
                  </span>
                </p>
              </button>
              <button
                type="button"
                onClick={() => onDelete(session.id)}
                aria-label={`Delete "${session.title}"`}
                className="shrink-0 rounded-md p-1 text-muted opacity-0 transition-opacity hover:bg-background hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100 max-md:opacity-100"
              >
                <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
                  <path
                    d="M6 6l8 8M14 6l-8 8"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
