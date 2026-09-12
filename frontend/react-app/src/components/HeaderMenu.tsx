import type { ReactNode } from "react"

interface HeaderMenuProps {
  label: string
  active: boolean
  onToggle: () => void
  /** Button content (the icon). */
  icon: ReactNode
  /** Extra glow ring, e.g. to mark the database icon. */
  glow?: boolean
}

/**
 * One navbar icon button. Its panel renders in the right-side dock
 * (see App), never as a dropdown under the bar, so open menus never
 * cover the messages column.
 */
export function HeaderMenu({ label, active, onToggle, icon, glow = false }: HeaderMenuProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-expanded={active}
      title={label}
      className={`rounded-full p-3 transition-all hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10 ${
        active ? "bg-black/5 text-foreground dark:bg-white/10" : "text-muted"
      } ${glow ? "text-primary drop-shadow-[0_0_6px_rgba(215,25,33,0.65)]" : ""}`}
    >
      {icon}
    </button>
  )
}
