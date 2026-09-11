import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent } from "react"
import useSWR from "swr"
import { AnimatedBackground } from "./components/AnimatedBackground"
import { AnimatedTitle } from "./components/AnimatedTitle"
import { ChatHistoryList } from "./components/ChatHistoryList"
import { ChatMessage } from "./components/ChatMessage"
import { Composer } from "./components/Composer"
import { DatabaseSelector } from "./components/DatabaseSelector"
import { LogoMark } from "./components/Logo"
import { SchemaSidebar } from "./components/SchemaSidebar"
import { askQuestion, fetchDatabases, fetchSchema, resetSession, uploadDatabase } from "./lib/api"
import { applyTheme, loadTheme, type Theme } from "./lib/theme"
import {
  loadSessions,
  saveSessions,
  sessionTitleFromEntries,
  type ChatSession,
} from "./lib/chatHistory"

const WIDTH_STORAGE_KEY = "rougyy.sidebarWidth"
const COLLAPSED_STORAGE_KEY = "rougyy.sidebarCollapsed"
const MIN_SIDEBAR_WIDTH = 240
const MAX_SIDEBAR_WIDTH = 460
const DEFAULT_SIDEBAR_WIDTH = 300

const SUGGESTIONS = [
  "How many singers are there?",
  "Which singers are from France?",
  "How many concerts were held at each stadium?",
]

function createSessionId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function loadNumber(key: string, fallback: number): number {
  try {
    const raw = window.localStorage.getItem(key)
    const parsed = raw ? Number(raw) : NaN
    return Number.isFinite(parsed) ? parsed : fallback
  } catch {
    return fallback
  }
}

function loadCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_STORAGE_KEY) === "1"
  } catch {
    return false
  }
}

function newSession(): ChatSession {
  const id = createSessionId()
  return { id, title: "New chat", createdAt: Date.now(), updatedAt: Date.now(), entries: [], dbIds: null }
}

export default function App() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const stored = loadSessions()
    return stored.length > 0 ? stored : [newSession()]
  })
  const [activeId, setActiveId] = useState<string>(() => loadSessions()[0]?.id ?? "")
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(loadCollapsed)
  const [theme, setTheme] = useState<Theme>(loadTheme)
  const [sidebarWidth, setSidebarWidth] = useState(() =>
    Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, loadNumber(WIDTH_STORAGE_KEY, DEFAULT_SIDEBAR_WIDTH))),
  )
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const resizingRef = useRef(false)

  // Keep the active session valid if the list changes underneath it.
  const active = useMemo(() => sessions.find((s) => s.id === activeId) ?? sessions[0], [sessions, activeId])
  const entries = active?.entries ?? []
  const selectedDbIds = active?.dbIds ?? null

  useEffect(() => {
    const timeoutId = window.setTimeout(() => saveSessions(sessions), 250)
    return () => window.clearTimeout(timeoutId)
  }, [sessions])

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const { data: databases, mutate: refreshDatabases } = useSWR("databases", () =>
    fetchDatabases().then((r) => r.databases),
  )

  const activeSchemaDbId = selectedDbIds?.length === 1 ? selectedDbIds[0] : undefined
  const {
    data: schema,
    isLoading: schemaLoading,
    error: schemaError,
    mutate: retrySchema,
  } = useSWR(["schema", activeSchemaDbId], () => fetchSchema(activeSchemaDbId), {
    shouldRetryOnError: false,
  })

  const lastLinkedTables = entries.at(-1)?.response?.linked_tables ?? []
  const isAsking = entries.some((entry) => entry.pending)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "auto" })
  }, [entries.length, activeId])

  const updateSession = useCallback((id: string, patch: (s: ChatSession) => ChatSession) => {
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...patch(s), updatedAt: Date.now() } : s)))
  }, [])

  async function handleAsk(question: string) {
    const target = active
    if (!target) return
    const entryId = createSessionId()
    updateSession(target.id, (s) => ({
      ...s,
      entries: [...s.entries, { id: entryId, question, response: null, pending: true, clientError: null }],
    }))
    setDrawerOpen(false)

    try {
      const response = await askQuestion(question, target.id, target.dbIds)
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== target.id) return s
          const nextEntries = s.entries.map((entry) =>
            entry.id === entryId ? { ...entry, response, pending: false } : entry,
          )
          return { ...s, entries: nextEntries, title: sessionTitleFromEntries(nextEntries), updatedAt: Date.now() }
        }),
      )
    } catch (error) {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== target.id) return s
          return {
            ...s,
            entries: s.entries.map((entry) =>
              entry.id === entryId
                ? { ...entry, pending: false, clientError: error instanceof Error ? error.message : String(error) }
                : entry,
            ),
            updatedAt: Date.now(),
          }
        }),
      )
    }
  }

  async function handleUpload(file: File) {
    setUploading(true)
    setUploadError(null)
    try {
      const added = await uploadDatabase(file)
      await refreshDatabases()
      if (active) updateSession(active.id, (s) => ({ ...s, dbIds: [added.id] }))
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : String(error))
    } finally {
      setUploading(false)
    }
  }

  function handleNewChat() {
    const session = newSession()
    setSessions((prev) => [session, ...prev])
    setActiveId(session.id)
    setDrawerOpen(false)
  }

  function handleSelectSession(id: string) {
    setActiveId(id)
    setDrawerOpen(false)
  }

  function handleDeleteSession(id: string) {
    void resetSession(id).catch(() => {})
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id)
      if (next.length === 0) {
        const fresh = newSession()
        queueMicrotask(() => setActiveId(fresh.id))
        return [fresh]
      }
      if (id === activeId) queueMicrotask(() => setActiveId(next[0].id))
      return next
    })
  }

  function handleToggleSidebar() {
    if (window.matchMedia("(max-width: 767px)").matches) {
      setDrawerOpen((open) => !open)
    } else {
      setCollapsed((prev) => {
        try {
          window.localStorage.setItem(COLLAPSED_STORAGE_KEY, prev ? "0" : "1")
        } catch {
          // ignore
        }
        return !prev
      })
    }
  }

  function handleResizeStart(event: ReactMouseEvent) {
    event.preventDefault()
    resizingRef.current = true
    const startX = event.clientX
    const startWidth = sidebarWidth

    function handleMove(moveEvent: MouseEvent) {
      if (!resizingRef.current) return
      const next = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, startWidth + moveEvent.clientX - startX))
      setSidebarWidth(next)
    }
    function handleUp() {
      resizingRef.current = false
      try {
        window.localStorage.setItem(WIDTH_STORAGE_KEY, String(sidebarWidthRef.current))
      } catch {
        // ignore
      }
      window.removeEventListener("mousemove", handleMove)
      window.removeEventListener("mouseup", handleUp)
    }
    window.addEventListener("mousemove", handleMove)
    window.addEventListener("mouseup", handleUp)
  }

  const sidebarWidthRef = useRef(sidebarWidth)
  sidebarWidthRef.current = sidebarWidth

  const sidebarStyle = useMemo(() => ({ "--sidebar-w": `${sidebarWidth}px` }) as CSSProperties, [sidebarWidth])

  return (
    <div className="relative flex h-screen flex-col bg-background text-foreground">
      <AnimatedBackground />

      <header className="glass relative z-20 mx-3 mt-3 flex items-center gap-2 rounded-2xl px-3 py-2.5">
        <button
          type="button"
          onClick={handleToggleSidebar}
          aria-label="Toggle sidebar"
          className="rounded-xl p-2 text-muted transition-colors hover:bg-black/5 hover:text-foreground"
        >
          <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
            <rect x="2.5" y="3.5" width="15" height="13" rx="2.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M8 3.5v13" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
        <div className="flex min-w-0 items-center gap-2.5">
          <LogoMark />
          <h1 className="min-w-0 truncate font-mono text-sm font-semibold tracking-tight text-foreground">
            rougyy
            <span className="ml-2 hidden truncate font-sans text-[11px] font-normal text-muted sm:inline">
              {active ? active.title : "Ask your database, in plain English"}
            </span>
          </h1>
        </div>
        <button
          type="button"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-xl p-2 text-muted transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
        >
          {theme === "dark" ? (
            <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
              <circle cx="10" cy="10" r="3.5" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M10 2.5v1.8M10 15.7v1.8M2.5 10h1.8M15.7 10h1.8M4.7 4.7l1.3 1.3M14 14l1.3 1.3M15.3 4.7 14 6M6 14l-1.3 1.3"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          ) : (
            <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
              <path
                d="M16.5 12.5A7 7 0 0 1 7.5 3.5a7 7 0 1 0 9 9Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </button>
        <button
          type="button"
          onClick={handleNewChat}
          className="flex items-center gap-1.5 rounded-full bg-primary px-3.5 py-1.5 text-[13px] font-medium text-primary-foreground shadow-md shadow-primary/30 transition-all hover:shadow-lg hover:brightness-110"
        >
          <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
            <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          <span className="hidden sm:inline">New chat</span>
        </button>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1 gap-3 p-3">
        {drawerOpen && (
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setDrawerOpen(false)}
            className="fixed inset-0 z-20 bg-black/40 md:hidden"
          />
        )}

        <aside
          style={sidebarStyle}
          className={`glass fixed inset-y-0 left-0 top-0 z-30 flex h-full shrink-0 flex-col overflow-hidden rounded-2xl transition-[width,transform] duration-200 ease-out md:static md:z-10 max-md:rounded-none max-md:border-0 max-md:pt-[76px] ${
            drawerOpen ? "translate-x-0" : "-translate-x-full"
          } w-[300px] md:w-[var(--sidebar-w)] md:translate-x-0 ${
            collapsed ? "md:w-0 md:border-0" : ""
          }`}
          aria-label="Sidebar"
          aria-hidden={collapsed}
          inert={collapsed}
        >
          <div className="flex h-full w-[300px] flex-col md:w-[var(--sidebar-w)]">
            <div className="flex-1 space-y-4 overflow-y-auto px-2 py-3">
              <section aria-label="Databases">
                <h2 className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Database
                </h2>
                <div className="px-1">
                  <DatabaseSelector
                    databases={databases ?? []}
                    selectedIds={selectedDbIds}
                    onSelect={(ids) => active && updateSession(active.id, (s) => ({ ...s, dbIds: ids }))}
                    onUpload={handleUpload}
                    uploading={uploading}
                    uploadError={uploadError}
                  />
                </div>
              </section>

              <section aria-label="Chat history">
                <h2 className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Chats
                </h2>
                <ChatHistoryList
                  sessions={sessions}
                  activeId={active?.id ?? ""}
                  onSelect={handleSelectSession}
                  onDelete={handleDeleteSession}
                />
              </section>

              <section aria-label="Schema" className="flex h-80 shrink-0 flex-col">
                <SchemaSidebar
                  dialect={schema?.dialect ?? null}
                  tables={schema?.tables ?? []}
                  linkedTables={lastLinkedTables}
                  loading={schemaLoading}
                  error={schemaError instanceof Error ? schemaError.message : schemaError ? String(schemaError) : null}
                  onRetry={() => retrySchema()}
                  databaseId={activeSchemaDbId}
                />
              </section>
            </div>

            <div className="border-t border-border px-4 py-2.5">
              <p className="text-[11px] leading-relaxed text-muted">
                Click a table for its full schema. Highlighted tables were linked to your last question.
              </p>
            </div>
          </div>

          {!collapsed && (
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize sidebar"
              onMouseDown={handleResizeStart}
              className="absolute inset-y-0 right-0 hidden w-1.5 cursor-col-resize touch-none transition-colors hover:bg-primary/40 md:block"
            />
          )}
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {entries.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center px-4 pb-10">
              <div className="w-full max-w-2xl text-center">
                <AnimatedTitle text="What do you want to know?" />
                <p className="mx-auto mt-2 max-w-md text-[13.5px] leading-relaxed text-muted">
                  Ask in plain English — Rougyy writes the SQL, runs it read-only, and answers from
                  real rows.
                </p>
                <div className="mt-6">
                  <Composer onSubmit={handleAsk} disabled={isAsking} large autoFocus />
                </div>
                <div className="mt-4 flex max-w-full flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => handleAsk(suggestion)}
                      disabled={isAsking}
                      className="glass rounded-full px-4 py-1.5 text-[12.5px] text-foreground transition-all hover:shadow-md disabled:opacity-50"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
                <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
                  {entries.map((entry) => (
                    <ChatMessage key={entry.id} entry={entry} />
                  ))}
                </div>
              </div>
              <div className="px-4 pb-4">
                <Composer onSubmit={handleAsk} disabled={isAsking} />
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  )
}
