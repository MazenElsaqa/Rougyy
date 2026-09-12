import { useEffect, useRef, useState, type KeyboardEvent } from "react"

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
  /** Hero mode: bigger type + padding for the centered empty-state composer. */
  large?: boolean
  autoFocus?: boolean
}

export function Composer({ onSubmit, disabled, large = false, autoFocus = false }: ComposerProps) {
  const [value, setValue] = useState("")
  const historyRef = useRef<string[]>(loadHistory())
  // -1 means "not currently browsing history" (the draft is the live value).
  const historyIndexRef = useRef(-1)
  const draftRef = useRef("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-grow up to max-h, then scroll internally.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${el.scrollHeight}px`
  }, [value])

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
    <div
      className={`glass-input mx-auto w-full transition-shadow focus-within:shadow-xl ${
        large ? "max-w-2xl rounded-[28px] p-2 pl-6" : "max-w-2xl rounded-[26px] p-1.5 pl-5"
      }`}
    >
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your database…"
          rows={large ? 2 : 1}
          disabled={disabled}
          autoFocus={autoFocus}
          className={`max-h-36 min-h-[42px] flex-1 resize-none overflow-y-auto bg-transparent leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-60 ${
            large ? "py-3 text-base" : "py-2.5 text-[15px]"
          }`}
        />
        <button
          type="button"
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Send question"
          className={`flex shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md shadow-primary/30 transition-all hover:shadow-lg hover:brightness-110 disabled:opacity-40 disabled:shadow-none ${
            large ? "h-11 w-11" : "h-[42px] w-[42px]"
          }`}
        >
          <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
            <path
              d="M10 16.5v-11m0 0L5.5 10M10 5.5 14.5 10"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
      {large && (
        <p className="px-1 pb-1 pt-1 text-center text-[11px] text-muted-foreground">
          Enter to send · Shift+Enter for a new line · ↑ recalls previous questions
        </p>
      )}
    </div>
  )
}
