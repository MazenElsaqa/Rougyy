import { useEffect, useRef, useState } from "react"
import useSWR from "swr"
import { ChatMessage, type ChatEntry } from "./components/ChatMessage"
import { Composer } from "./components/Composer"
import { SchemaSidebar } from "./components/SchemaSidebar"
import { askQuestion, fetchSchema, resetSession } from "./lib/api"

function createSessionId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export default function App() {
  const [sessionId, setSessionId] = useState(createSessionId)
  const [entries, setEntries] = useState<ChatEntry[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const { data: schema, isLoading: schemaLoading, error: schemaError, mutate: retrySchema } = useSWR("schema", fetchSchema, {
    shouldRetryOnError: false,
  })

  const lastLinkedTables = entries.at(-1)?.response?.linked_tables ?? []
  const isAsking = entries.some((entry) => entry.pending)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [entries])

  async function handleAsk(question: string) {
    const id = createSessionId()
    setEntries((prev) => [...prev, { id, question, response: null, pending: true, clientError: null }])
    setSidebarOpen(false)

    try {
      const response = await askQuestion(question, sessionId)
      setEntries((prev) =>
        prev.map((entry) => (entry.id === id ? { ...entry, response, pending: false } : entry)),
      )
    } catch (error) {
      setEntries((prev) =>
        prev.map((entry) =>
          entry.id === id
            ? { ...entry, pending: false, clientError: error instanceof Error ? error.message : String(error) }
            : entry,
        ),
      )
    }
  }

  async function handleNewChat() {
    await resetSession(sessionId).catch(() => {})
    setSessionId(createSessionId())
    setEntries([])
  }

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            className="rounded-md p-1.5 text-muted hover:bg-surface-muted md:hidden"
            aria-label="Toggle schema sidebar"
          >
            <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
              <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
          <div>
            <h1 className="font-mono text-sm font-semibold tracking-tight text-foreground">rougyy</h1>
            <p className="hidden text-[11px] text-muted sm:block">Ask your database, in plain English</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleNewChat}
          className="rounded-md border border-border px-3 py-1.5 text-[13px] font-medium text-foreground hover:bg-surface-muted"
        >
          New chat
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div
          className={`absolute inset-y-0 left-0 z-10 w-64 transform transition-transform md:relative md:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <SchemaSidebar
            dialect={schema?.dialect ?? null}
            tables={schema?.tables ?? []}
            linkedTables={lastLinkedTables}
            loading={schemaLoading}
            error={schemaError instanceof Error ? schemaError.message : schemaError ? String(schemaError) : null}
            onRetry={() => retrySchema()}
          />
        </div>

        <main className="flex flex-1 flex-col overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
            <div className="mx-auto flex max-w-3xl flex-col gap-5">
              {entries.length === 0 && (
                <div className="mt-10 flex flex-col items-center gap-2 text-center">
                  <p className="text-sm font-medium text-foreground">
                    Ask a question about {schema?.tables.length ?? "your"} database tables
                  </p>
                  <p className="max-w-sm text-[13px] leading-relaxed text-muted">
                    Rougyy turns your question into SQL, validates and runs it read-only, then answers
                    from the actual rows returned.
                  </p>
                </div>
              )}
              {entries.map((entry) => (
                <ChatMessage key={entry.id} entry={entry} />
              ))}
            </div>
          </div>
          <Composer onSubmit={handleAsk} disabled={isAsking} />
        </main>
      </div>
    </div>
  )
}
