import type { ReactNode } from "react"

interface HeaderMenuProps {
  label: string;
  active: boolean;
  onToggle: () => void;
  /** Button content (the icon). */
  icon: ReactNode;
  /** Extra glow ring, e.g. to mark the database icon. */
  glow?: boolean;
  /** Tour spotlight: lit up, bigger, and glowing while its feature is toured. */
  spotlit?: boolean;
  /** Tour dimming: muted while another navbar feature is toured. */
  dimmed?: boolean;
}

/**
 * One navbar icon button. Its panel renders in the right-side dock
 * (see App), never as a dropdown under the bar, so open menus never
 * cover the messages column.
 */
export function HeaderMenu({ label, active, onToggle, icon, glow = false, spotlit = false, dimmed = false }: HeaderMenuProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-expanded={active}
      title={label}
      className={`rounded-full p-3 transition-all hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10 ${
        active ? "bg-black/5 text-foreground dark:bg-white/10" : "text-muted"
      } ${glow ? "text-primary drop-shadow-[0_0_6px_rgba(215,25,33,0.65)]" : ""} ${
        spotlit ? "scale-125 bg-primary-muted text-primary shadow-[0_0_22px_rgba(215,25,33,0.55)]" : ""
      } ${dimmed && !spotlit ? "opacity-40 saturate-50" : ""}`}
    >
      {icon}
    </button>
  )
}
