import { useEffect } from "react";
import { TOUR_STEPS } from "./steps";

interface TourProps {
  index: number;
  onGo: (index: number) => void;
  onClose: () => void;
}

/**
 * The tour tooltip: bottom-center glass card with progress, the step
 * copy, and navigation. The dim overlay is pointer-transparent so the
 * live UI underneath stays clickable — every step is performed for
 * real, nothing here is a screenshot or mock. Arrow keys navigate.
 */
export function Tour({ index, onGo, onClose }: TourProps) {
  const step = TOUR_STEPS[index];
  const last = index === TOUR_STEPS.length - 1;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "ArrowRight") {
        event.preventDefault();
        if (last) onClose();
        else onGo(index + 1);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        if (index > 0) onGo(index - 1);
      } else if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [index, last, onGo, onClose]);

  return (
    <div className="pointer-events-none fixed inset-0 z-[60] flex items-end justify-center p-4 lg:items-center lg:justify-start lg:p-6">
      <div className="glass-strong pointer-events-auto flex max-h-[52vh] w-full max-w-xl flex-col overflow-hidden rounded-3xl lg:max-h-[80vh] lg:w-[340px] lg:max-w-none lg:shadow-2xl lg:shadow-primary/20">
        <div className="h-1 shrink-0 bg-black/5 dark:bg-white/10">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300"
            style={{ width: `${((index + 1) / TOUR_STEPS.length) * 100}%` }}
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-primary">
              Step {index + 1} of {TOUR_STEPS.length}
            </p>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-2 py-1 text-[12px] font-medium text-muted transition-colors hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
            >
              Skip tour
            </button>
          </div>

          <h3 className="mt-1 text-lg font-bold tracking-tight text-foreground">{step.title}</h3>
          <p className="mt-1 text-[13.5px] leading-relaxed text-muted">{step.body}</p>
        </div>

        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border/60 px-4 py-3">
          <div className="flex max-w-[35%] items-center gap-1 overflow-x-auto">
            {TOUR_STEPS.map((s, i) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onGo(i)}
                aria-label={`Go to step ${i + 1}: ${s.title}`}
                title={s.title}
                className={`h-1.5 shrink-0 rounded-full transition-all ${
                  i === index ? "w-5 bg-primary" : "w-1.5 bg-border hover:bg-muted"
                }`}
              />
            ))}
          </div>
          <p className="hidden text-[11px] text-muted-foreground xl:block">← → to move</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onGo(index - 1)}
              disabled={index === 0}
              className="rounded-full border border-border bg-surface px-4 py-1.5 text-[13px] font-medium text-foreground transition-all hover:shadow disabled:opacity-40"
            >
              Back
            </button>
            {last ? (
              <button
                type="button"
                onClick={onClose}
                className="rounded-full bg-primary px-5 py-1.5 text-[13px] font-medium text-primary-foreground shadow-md shadow-primary/30 transition-all hover:brightness-110"
              >
                Start chatting
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onGo(index + 1)}
                className="rounded-full bg-primary px-5 py-1.5 text-[13px] font-medium text-primary-foreground shadow-md shadow-primary/30 transition-all hover:brightness-110"
              >
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
