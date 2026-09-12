import { useEffect, useMemo, useState } from "react"

interface GuideStep {
  target: string
  title: string
  description: string
  action: string
}

interface UserGuideProps {
  open: boolean
  onClose: () => void
  steps: GuideStep[]
}

export function UserGuide({ open, onClose, steps }: UserGuideProps) {
  const [stepIndex, setStepIndex] = useState(0)
  const step = steps[stepIndex]

  useEffect(() => {
    if (!open) return
    setStepIndex(0)
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = ""
    }
  }, [open])

  const targetRect = useMemo(() => {
    if (!open || !step) return null
    const target = document.querySelector(`[data-guide-target="${step.target}"]`)
    return target?.getBoundingClientRect() ?? null
  }, [open, step])

  useEffect(() => {
    if (!open || !step) return
    const target = document.querySelector(`[data-guide-target="${step.target}"]`)
    target?.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" })
  }, [open, step])

  if (!open || !step) return null

  const isLast = stepIndex === steps.length - 1
  const panelTop = targetRect ? Math.min(Math.max(targetRect.bottom + 18, 88), window.innerHeight - 235) : 120
  const panelLeft = targetRect ? Math.min(Math.max(targetRect.left, 18), window.innerWidth - 370) : 18

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="guide-title">
      <div className="absolute inset-0 bg-foreground/35 backdrop-blur-[2px]" onClick={onClose} aria-hidden="true" />
      {targetRect && (
        <div
          className="pointer-events-none absolute rounded-2xl border-2 border-primary shadow-[0_0_0_9999px_rgba(0,0,0,0.36),0_0_28px_rgba(215,25,33,0.45)] transition-all duration-300"
          style={{ left: targetRect.left - 8, top: targetRect.top - 8, width: targetRect.width + 16, height: targetRect.height + 16 }}
          aria-hidden="true"
        />
      )}
      <section
        className="glass-strong absolute w-[calc(100vw-2rem)] max-w-[350px] rounded-2xl p-5 shadow-2xl transition-all duration-300"
        style={{ top: panelTop, left: panelLeft }}
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">DIDA guide</p>
          <button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-xs text-muted transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10">Skip</button>
        </div>
        <h2 id="guide-title" className="text-lg font-bold text-foreground">{step.title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">{step.description}</p>
        <p className="mt-3 rounded-lg bg-primary-muted px-3 py-2 text-xs leading-relaxed text-foreground">{step.action}</p>
        <div className="mt-5 flex items-center justify-between gap-3">
          <span className="text-xs text-muted">Step {stepIndex + 1} of {steps.length}</span>
          <div className="flex items-center gap-2">
            <button type="button" disabled={stepIndex === 0} onClick={() => setStepIndex((current) => current - 1)} className="rounded-lg border border-border px-3 py-2 text-xs font-medium text-foreground transition-colors hover:bg-black/5 disabled:opacity-40 dark:hover:bg-white/10">Back</button>
            <button type="button" onClick={() => isLast ? onClose() : setStepIndex((current) => current + 1)} className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md shadow-primary/25 transition-all hover:brightness-110">{isLast ? "Finish" : "Next"}</button>
          </div>
        </div>
      </section>
    </div>
  )
}

export type { GuideStep }
