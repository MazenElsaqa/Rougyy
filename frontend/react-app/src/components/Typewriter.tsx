import { useEffect, useState } from "react"

interface TypewriterProps {
  /** Lines are typed in order, each on its own row. */
  lines: string[]
  /** ms per character while typing */
  speed?: number
  /** ms per character while deleting (loop mode) */
  deleteSpeed?: number
  /** pause at full text before deleting (loop mode) */
  holdMs?: number
  /** when true, loop forever: type -> hold -> delete -> retype */
  loop?: boolean
  className?: string
}

/** Types `lines` out character by character with a blinking block caret. */
export function Typewriter({
  lines,
  speed = 75,
  deleteSpeed = 35,
  holdMs = 2200,
  loop = false,
  className = "",
}: TypewriterProps) {
  const full = lines.join("\n")
  const [length, setLength] = useState(0)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    setLength(0)
    setDeleting(false)
  }, [full])

  useEffect(() => {
    if (!full) return
    let timer: number
    if (!deleting && length >= full.length) {
      if (!loop) return
      timer = window.setTimeout(() => setDeleting(true), holdMs)
    } else if (deleting && length <= 0) {
      timer = window.setTimeout(() => setDeleting(false), 700)
    } else {
      timer = window.setTimeout(
        () => setLength((prev) => prev + (deleting ? -1 : 1)),
        deleting ? deleteSpeed : speed,
      )
    }
    return () => window.clearTimeout(timer)
  }, [length, deleting, full, speed, deleteSpeed, holdMs, loop])

  const visible = full.slice(0, length).split("\n")

  return (
    <span className={className} aria-label={full}>
      {visible.map((line, i) => (
        <span key={i} aria-hidden="true" className="block">
          {line}
          {i === visible.length - 1 && (
            <span
              aria-hidden="true"
              className="ml-1 inline-block h-[0.9em] w-[4px] translate-y-[3px] animate-pulse rounded-full bg-primary"
            />
          )}
        </span>
      ))}
    </span>
  )
}
