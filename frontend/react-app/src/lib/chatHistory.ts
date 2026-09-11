import type { ChatEntry } from "../components/ChatMessage"

export interface ChatSession {
  /** doubles as the backend session_id, so memory keeps working */
  id: string
  title: string
  createdAt: number
  updatedAt: number
  entries: ChatEntry[]
  dbIds: string[] | null
}

const STORAGE_KEY = "rougyy.chatSessions"
const MAX_SESSIONS = 15
const MAX_ENTRIES_PER_SESSION = 30

export function sessionTitleFromEntries(entries: ChatEntry[]): string {
  const first = entries.find((e) => e.question.trim())
  if (!first) return "New chat"
  const title = first.question.trim().replace(/\s+/g, " ")
  return title.length > 44 ? `${title.slice(0, 44)}…` : title
}

export function loadSessions(): ChatSession[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ChatSession[]
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((s) => s && typeof s.id === "string" && Array.isArray(s.entries))
      .slice(0, MAX_SESSIONS)
  } catch {
    return []
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  try {
    const trimmed = sessions.slice(0, MAX_SESSIONS).map((s) => ({
      ...s,
      entries: s.entries.slice(-MAX_ENTRIES_PER_SESSION),
    }))
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    // private mode / quota full -- history just won't persist
  }
}

export function timeAgo(timestamp: number): string {
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
  if (seconds < 60) return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(timestamp).toLocaleDateString()
}
