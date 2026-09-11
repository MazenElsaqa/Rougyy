import { useRef, useState, type KeyboardEvent } from "react"

const HISTORY_STORAGE_KEY = "rougyy.questionHistory"
const MAX_HISTORY = 50

function loadHistory(): string[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function saveHistory(history: string[]) {
  try {
    window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history.slice(-MAX_HISTORY)))
  } catch {
    // ignore (private mode, storage full, etc.)
  }
}

interface ComposerProps {
  onSubmit: (question: string) => void
  disabled: boolean
}

export function Composer({ onSubmit, disabled }: ComposerProps) {
  const [value, setValue] = useState("")
  const historyRef = useRef<string[]>(loadHistory())
  // -1 means "not currently browsing history" (the draft is the live value).
  const historyIndexRef = useRef(-1)
  const draftRef = useRef("")

  function submit() {
    const question = value.trim()
    if (!question || disabled) return
    onSubmit(question)
    setValue("")

    const history = historyRef.current
    if (history.at(-1) !== question) {
      history.push(question)
      saveHistory(history)
    }
    historyIndexRef.current = -1
    draftRef.current = ""
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Avoid submitting mid-IME composition (CJK input), and Safari's
    // unreliable final composition event which reports keyCode 229.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault()
      submit()
      return
    }

    // Command-bar style history recall: Up/Down cycle through
    // previously sent questions, most recent first. Only trigger when
    // the cursor is on the first (Up) or last (Down) line, so users
    // can still move the cursor within a multi-line draft normally.
    const textarea = event.currentTarget
    const history = historyRef.current
    if (event.key === "ArrowUp") {
      const caretOnFirstLine = textarea.selectionStart <= (value.indexOf("\n") === -1 ? value.length : value.indexOf("\n"))
      if (!caretOnFirstLine || history.length === 0) return
      event.preventDefault()
      if (historyIndexRef.current === -1) {
        draftRef.current = value
        historyIndexRef.current = history.length - 1
      } else if (historyIndexRef.current > 0) {
        historyIndexRef.current -= 1
      }
      setValue(history[historyIndexRef.current])
    } else if (event.key === "ArrowDown") {
      if (historyIndexRef.current === -1) return
      const caretOnLastLine = textarea.selectionStart >= value.lastIndexOf("\n") + 1
      if (!caretOnLastLine) return
      event.preventDefault()
      if (historyIndexRef.current < history.length - 1) {
        historyIndexRef.current += 1
        setValue(history[historyIndexRef.current])
      } else {
        historyIndexRef.current = -1
        setValue(draftRef.current)
      }
    }
  }

  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about the database…"
          rows={1}
          disabled={disabled}
          className="max-h-32 flex-1 resize-none rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none disabled:opacity-60"
        />
        <button
          type="button"
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="shrink-0 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-40"
        >
          Ask
        </button>
      </div>
    </div>
  )
}
