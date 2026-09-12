import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { AnimatedBackground } from "./components/AnimatedBackground"
import { AnimatedTitle } from "./components/AnimatedTitle"
import { ChatHistoryList } from "./components/ChatHistoryList"
import { ChatMessage, type ChatEntry } from "./components/ChatMessage"
import { Composer } from "./components/Composer"
import { DatabaseMenu } from "./components/DatabaseMenu"
import { HeaderMenu } from "./components/HeaderMenu"
import { CatCompanion, type Mood } from "./components/CatCompanion"
import { SchemaSidebar } from "./components/SchemaSidebar"
import { SqlEditor } from "./components/SqlEditor"
import { Typewriter } from "./components/Typewriter"
import { UserGuide, type GuideStep } from "./components/UserGuide"
import { askQuestion, cancelAsk, fetchDatabases, fetchSchema, resetSession, uploadDatabase } from "./lib/api"
import { applyTheme, loadTheme, type Theme } from "./lib/theme"
import {
  loadSessions,
  saveSessions,
  sessionTitleFromEntries,
  type ChatSession,
} from "./lib/chatHistory"

const SUGGESTIONS = [
  "How many singers are there?",
  "Which singers are from France?",
  "How many concerts were held at each stadium?",
]

const GUIDE_STEPS: GuideStep[] = [
  { target: "database-menu", title: "Choose your data", description: "Start by opening the database menu to see the available databases.", action: "Use All databases to search everything, or select one database for a focused answer." },
  { target: "database-menu", title: "Add your own database", description: "Bring your own SQLite, CSV, or spreadsheet into DIDA.", action: "Open the database menu, choose Add your own database, then select a supported file." },
  { target: "question-composer", title: "Ask in plain English", description: "Tell DIDA what you want to learn without writing SQL yourself.", action: "Type a question or choose one of the suggested questions below the composer." },
  { target: "chat-history", title: "Keep your conversations", description: "Every question and answer is grouped into a chat you can revisit.", action: "Open Chat history to switch between chats, start a new one, or delete an old one." },
  { target: "schema-menu", title: "Explore the schema", description: "See the tables and columns available in the selected database.", action: "Open Database schema whenever you need context before asking a question." },
  { target: "sql-menu", title: "Use SQL directly", description: "For advanced users, the SQL editor lets you run read-only queries directly.", action: "Open SQL editor, choose a table, write your query, and run it when ready." },
]

type OpenMenu = null | "db" | "sql" | "chats" | "schema"

function createSessionId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function newSession(): ChatSession {
  const id = createSessionId()
  return { id, title: "New chat", createdAt: Date.now(), updatedAt: Date.now(), entries: [], dbIds: null }
}

/**
 * DIDA's mood for the brand face: excited while working, sad when the
 * last turn failed or was cancelled, happy after lots of successful
 * answers, neutral otherwise.
 */
function moodForEntries(entries: ChatEntry[]): Mood {
  if (entries.some((entry) => entry.pending)) return "happy"
  const done = entries.filter((entry) => entry.response || entry.clientError)
  if (done.length === 0) return "normal"
  const last = done[done.length - 1]
  if (last.clientError) return "sad"
  return done.filter((entry) => entry.response && !entry.response.error).length >= 3 ? "happy" : "normal"
}

export default function App() {
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const stored = loadSessions()
    return stored.length > 0 ? stored : [newSession()]
  })
  const [activeId, setActiveId] = useState<string>(() => loadSessions()[0]?.id ?? "")
  const [openMenu, setOpenMenu] = useState<OpenMenu>(null)
  const [guideOpen, setGuideOpen] = useState(false)
  const [catSide, setCatSide] = useState<"left" | "right">(() => {
    try {
      return window.localStorage.getItem("rougyy.catSide") === "left" ? "left" : "right"
    } catch {
      return "right"
    }
  })
  const [theme, setTheme] = useState<Theme>(loadTheme)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const pendingControllers = useRef(new Map<string, AbortController>())

  // Draggable cat position: null = docked to a corner, otherwise exact
  // viewport coords. Tracked manually (not framer drag) so a real drag
  // can never be mistaken for a tap.
  const [catPos, setCatPos] = useState<{ x: number; y: number } | null>(() => {
    try {
      const raw = window.localStorage.getItem("rougyy.catPos")
      if (raw) {
        const saved = JSON.parse(raw) as { x: number; y: number }
        if (Number.isFinite(saved.x) && Number.isFinite(saved.y)) return saved
      }
    } catch {
      // ignore
    }
    return null
  })
  const catDrag = useRef<{ startX: number; startY: number; origX: number; origY: number; moved: boolean } | null>(null)
  const catBoxRef = useRef<HTMLDivElement>(null)

  function clampCat(x: number, y: number): { x: number; y: number } {
    const box = catBoxRef.current?.getBoundingClientRect()
    const w = box?.width ?? 120
    const h = box?.height ?? 140
    return {
      x: Math.max(-w + 48, Math.min(window.innerWidth - 48, x)),
      y: Math.max(0, Math.min(Math.max(0, window.innerHeight - h), y)),
    }
  }

  function moveCatToOtherCorner() {
    try {
      window.localStorage.removeItem("rougyy.catPos")
    } catch {
      // ignore
    }
    setCatPos(null)
    setCatSide((prev) => {
      const next = prev === "right" ? "left" : "right"
      try {
        window.localStorage.setItem("rougyy.catSide", next)
      } catch {
        // ignore
      }
      return next
    })
  }

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

  useEffect(() => {
    if (!openMenu) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpenMenu(null)
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [openMenu])

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
    const controller = new AbortController()
    pendingControllers.current.set(entryId, controller)
    updateSession(target.id, (s) => ({
      ...s,
      entries: [...s.entries, { id: entryId, question, response: null, pending: true, clientError: null }],
    }))

    try {
      const response = await askQuestion(question, target.id, target.dbIds, controller.signal)
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
      const cancelled = controller.signal.aborted
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== target.id) return s
          return {
            ...s,
            entries: s.entries.map((entry) =>
              entry.id === entryId
                ? {
                    ...entry,
                    pending: false,
                    clientError: cancelled
                      ? "Cancelled."
                      : error instanceof Error
                        ? error.message
                        : String(error),
                  }
                : entry,
            ),
            updatedAt: Date.now(),
          }
        }),
      )
    } finally {
      pendingControllers.current.delete(entryId)
    }
  }

  function handleCancel(entryId: string) {
    // 1. Drop the HTTP request instantly (UI frees up right away).
    pendingControllers.current.get(entryId)?.abort()
    // 2. Tell the server to stop the pipeline before its next LLM
    //    call, so it doesn't burn retries or pollute memory.
    const owner = sessions.find((s) => s.entries.some((e) => e.id === entryId))
    if (owner) void cancelAsk(owner.id)
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
    setOpenMenu(null)
  }

  function handleSelectSession(id: string) {
    setActiveId(id)
    setOpenMenu(null)
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

  function toggleMenu(menu: Exclude<OpenMenu, null>) {
    setOpenMenu((prev) => (prev === menu ? null : menu))
  }

  return (
    <div className="relative flex h-screen flex-col bg-background text-foreground">
      <AnimatedBackground />

      <div className="absolute left-4 top-4 z-20 select-none">
        <span className="text-2xl font-extrabold tracking-tight text-foreground">
          dida<span className="text-primary">.</span>
        </span>
        <div className="mt-1 hidden min-[500px]:block">
          <Typewriter
            lines={["heyy", "zeinn.."]}
            speed={130}
            deleteSpeed={45}
            holdMs={2400}
            loop
            className="bg-gradient-to-r from-primary to-[#ff7a59] bg-clip-text font-hand text-5xl font-bold leading-[1.05]"
          />
        </div>
      </div>

      <header className="glass-nav relative z-20 mx-auto mt-3 flex w-fit max-w-[calc(100vw-1.5rem)] items-center gap-2 rounded-full px-4 py-2.5">
        <div data-guide-target="database-menu">
        <HeaderMenu
          label={`Database: ${selectedDbIds === null ? "all databases" : databases?.find((d) => d.id === selectedDbIds[0])?.name ?? "select"}`}
          active={openMenu === "db"}
          onToggle={() => toggleMenu("db")}
          glow
          icon={
            <svg viewBox="0 0 20 20" fill="none" className="h-7 w-7" aria-hidden="true">
              <ellipse cx="10" cy="5" rx="6" ry="2.2" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M4 5v5c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2V5M4 10v5c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2v-5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          }
        />
        </div>

        <div data-guide-target="sql-menu">
        <HeaderMenu
          label="SQL editor"
          active={openMenu === "sql"}
          onToggle={() => toggleMenu("sql")}
          icon={
            <svg viewBox="0 0 20 20" fill="none" className="h-7 w-7" aria-hidden="true">
              <path
                d="M7 6 3.5 10 7 14M13 6l3.5 4L13 14"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          }
        />
        </div>

        <div data-guide-target="chat-history">
        <HeaderMenu
          label="Chat history"
          active={openMenu === "chats"}
          onToggle={() => toggleMenu("chats")}
          icon={
            <svg viewBox="0 0 20 20" fill="none" className="h-7 w-7" aria-hidden="true">
              <path
                d="M3.5 5.5h13v8h-8l-3.5 3v-3H3.5v-8Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
              <path d="M7 8.5h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          }
        />
        </div>

        <div data-guide-target="schema-menu">
        <HeaderMenu
          label="Database schema"
          active={openMenu === "schema"}
          onToggle={() => toggleMenu("schema")}
          icon={
            <svg viewBox="0 0 20 20" fill="none" className="h-7 w-7" aria-hidden="true">
              <rect x="3" y="4" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M3 8h14M8 8v8" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          }
        />
        </div>
        <button
          type="button"
          onClick={() => setGuideOpen(true)}
          aria-label="Open user guide"
          title="User guide"
          className="rounded-full p-2.5 text-muted transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
        >
          <span className="flex size-7 items-center justify-center rounded-full border border-current text-sm font-bold">?</span>
        </button>
        <button
          type="button"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-full p-2.5 text-muted transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
        >
          {theme === "dark" ? (
            <svg viewBox="0 0 20 20" fill="none" className="h-7 w-7" aria-hidden="true">
              <circle cx="10" cy="10" r="3.5" stroke="currentColor" strokeWidth="1.5" />
              <path
                d="M10 2.5v1.8M10 15.7v1.8M2.5 10h1.8M15.7 10h1.8M4.7 4.7l1.3 1.3M14 14l1.3 1.3M15.3 4.7 14 6M6 14l-1.3 1.3"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          ) : (
            <svg viewBox="0 0 20 20" fill="none" className="h-7 w-7" aria-hidden="true">
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
          aria-label="New chat"
          title="New chat"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md shadow-primary/30 transition-all hover:shadow-lg hover:brightness-110"
        >
          <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
            <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      {openMenu && (
        <div
          className="glass-strong absolute bottom-3 right-3 top-[84px] z-30 flex w-[340px] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-2xl"
          role="dialog"
          aria-label={openMenu === "db" ? "Databases" : openMenu === "chats" ? "Chat history" : "Database schema"}
        >
          <div className="flex items-center justify-between border-b border-border/60 px-4 py-2.5">
            <h2 className="text-[13px] font-semibold text-foreground">
              {openMenu === "db"
                ? "Databases"
                : openMenu === "sql"
                  ? "SQL editor"
                  : openMenu === "chats"
                    ? "Chats"
                    : "Schema"}
            </h2>
            <button
              type="button"
              onClick={() => setOpenMenu(null)}
              aria-label="Close panel"
              className="rounded-lg p-1.5 text-muted transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
            >
              <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
                <path d="M6 6l8 8M14 6l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {openMenu === "db" && (
              <DatabaseMenu
                databases={databases ?? []}
                selectedIds={selectedDbIds}
                onSelect={(ids) => {
                  if (active) updateSession(active.id, (s) => ({ ...s, dbIds: ids }))
                  setOpenMenu(null)
                }}
                onUpload={handleUpload}
                uploading={uploading}
                uploadError={uploadError}
              />
            )}
            {openMenu === "chats" && (
              <div>
                <div className="mb-1 flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => {
                      handleNewChat()
                      setOpenMenu(null)
                    }}
                    className="flex flex-1 items-center gap-2 rounded-xl bg-primary px-3 py-2 text-[13px] font-medium text-primary-foreground shadow-md shadow-primary/30 transition-all hover:brightness-110"
                  >
                    <svg viewBox="0 0 20 20" fill="none" className="h-3.5 w-3.5" aria-hidden="true">
                      <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    </svg>
                    New chat
                  </button>
                  <button
                    type="button"
                    onClick={() => active && handleDeleteSession(active.id)}
                    aria-label="Delete current chat"
                    title="Delete current chat"
                    className="rounded-xl p-2 text-muted transition-colors hover:bg-destructive-muted hover:text-destructive"
                  >
                    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
                      <path
                        d="M4 5.5h12M8 5V4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1M6.5 5.5l.7 9a1.5 1.5 0 0 0 1.5 1.4h2.6a1.5 1.5 0 0 0 1.5-1.4l.7-9"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </div>
                <ChatHistoryList
                  sessions={sessions}
                  activeId={active?.id ?? ""}
                  onSelect={handleSelectSession}
                  onDelete={handleDeleteSession}
                />
              </div>
            )}
            {openMenu === "schema" && (
              <div className="h-full min-h-[300px]">
                <SchemaSidebar
                  dialect={schema?.dialect ?? null}
                  tables={schema?.tables ?? []}
                  linkedTables={lastLinkedTables}
                  loading={schemaLoading}
                  error={
                    schemaError instanceof Error ? schemaError.message : schemaError ? String(schemaError) : null
                  }
                  onRetry={() => retrySchema()}
                  databaseId={activeSchemaDbId}
                />
              </div>
            )}
            {openMenu === "sql" && (
              <SqlEditor
                databaseId={activeSchemaDbId}
                databaseName={
                  selectedDbIds?.length === 1
                    ? (databases?.find((d) => d.id === selectedDbIds[0])?.name ?? "selected")
                    : "default"
                }
                defaultTable={schema?.tables[0]?.name ?? null}
              />
            )}
          </div>
        </div>
      )}

      <div className="relative z-10 flex min-h-0 flex-1 p-3">
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {entries.length === 0 ? (
            <div className="flex flex-1 flex-col px-4 pb-10 pt-6">
              <div className="flex flex-1 flex-col items-center justify-center">
                <div className="w-full max-w-2xl text-center">
                  <AnimatedTitle text="What do you want to know?" />
                  <p className="mx-auto mt-2 max-w-md text-[13.5px] leading-relaxed text-muted">
                    Ask in plain English — DIDA writes the SQL, runs it read-only, and answers from
                    real rows.
                  </p>
                <div className="mt-6" data-guide-target="question-composer">
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
          </div>
          ) : (
            <>
              <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
                <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
                  {entries.map((entry) => (
                    <ChatMessage key={entry.id} entry={entry} onCancel={handleCancel} />
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

      <div
        className={`pointer-events-none fixed z-40 ${
          catPos ? "" : `bottom-5 md:bottom-6 ${catSide === "right" ? "right-5 md:right-6" : "left-5 md:left-6"}`
        }`}
        style={catPos ? { left: catPos.x, top: catPos.y } : undefined}
      >
        <div
          ref={catBoxRef}
          role="button"
          tabIndex={0}
          aria-label="DIDA the cat. Drag her anywhere, or activate to move her to the other corner."
          onPointerDown={(event) => {
            const box = catBoxRef.current?.getBoundingClientRect()
            catDrag.current = {
              startX: event.clientX,
              startY: event.clientY,
              origX: box?.left ?? 0,
              origY: box?.top ?? 0,
              moved: false,
            }
            event.currentTarget.setPointerCapture(event.pointerId)
          }}
          onPointerMove={(event) => {
            const drag = catDrag.current
            if (!drag) return
            const dx = event.clientX - drag.startX
            const dy = event.clientY - drag.startY
            if (!drag.moved && Math.hypot(dx, dy) < 6) return
            drag.moved = true
            setCatPos(clampCat(drag.origX + dx, drag.origY + dy))
          }}
          onPointerUp={() => {
            const drag = catDrag.current
            catDrag.current = null
            if (!drag) return
            if (!drag.moved) {
              moveCatToOtherCorner()
            } else {
              try {
                const box = catBoxRef.current?.getBoundingClientRect()
                if (box) {
                  const pos = clampCat(box.left, box.top)
                  setCatPos(pos)
                  window.localStorage.setItem("rougyy.catPos", JSON.stringify(pos))
                }
              } catch {
                // ignore
              }
            }
          }}
          onPointerCancel={() => {
            catDrag.current = null
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault()
              moveCatToOtherCorner()
            }
          }}
          className="pointer-events-auto touch-none select-none rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <CatCompanion mood={moodForEntries(entries)} className="h-24 w-auto md:h-32" />
        </div>
      </div>

      <UserGuide open={guideOpen} onClose={() => setGuideOpen(false)} steps={GUIDE_STEPS} />
    </div>
  )
}
