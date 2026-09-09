import { useState, type KeyboardEvent } from "react"

interface ComposerProps {
  onSubmit: (question: string) => void
  disabled: boolean
}

export function Composer({ onSubmit, disabled }: ComposerProps) {
  const [value, setValue] = useState("")

  function submit() {
    const question = value.trim()
    if (!question || disabled) return
    onSubmit(question)
    setValue("")
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Avoid submitting mid-IME composition (CJK input), and Safari's
    // unreliable final composition event which reports keyCode 229.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault()
      submit()
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
