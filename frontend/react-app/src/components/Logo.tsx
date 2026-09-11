/**
 * Brand mark: an Elsewedy-red rounded square with a white energy bolt.
 * Drop a real logo file at `public/logo.png` later and swap this `<svg>`
 * for `<img src="/logo.png">` -- the layout already reserves the slot.
 */
export function LogoMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-[9px] bg-primary shadow-md shadow-primary/40 ${className}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 20 20" fill="none" className="h-[62%] w-[62%]">
        <path
          d="M11.2 1.8 4.4 11.2h4.1l-1.3 6.9 6.9-9.9H9.9l1.3-6.4Z"
          fill="white"
          stroke="white"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}
