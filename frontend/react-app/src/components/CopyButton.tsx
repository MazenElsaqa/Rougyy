import { useState } from "react"

interface CopyButtonProps {
  text: string
  label: string
}

export function CopyButton({ text, label }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Clipboard API unavailable (permissions, insecure context) -- fallback.
      const area = document.createElement("textarea")
      area.value = text
      document.body.appendChild(area)
      area.select()
      document.execCommand("copy")
      area.remove()
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={label}
      title={copied ? "Copied!" : "Copy"}
      className="rounded-md p-1.5 text-muted transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
    >
      {copied ? (
        <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 text-primary" aria-hidden="true">
          <path d="M4.5 10.5 8.5 14.5 15.5 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
          <rect x="7" y="7" width="9" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" />
          <path d="M13 7V5.5A1.5 1.5 0 0 0 11.5 4h-6A1.5 1.5 0 0 0 4 5.5v6A1.5 1.5 0 0 0 5.5 13H7" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      )}
    </button>
  )
}
