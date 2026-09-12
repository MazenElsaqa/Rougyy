import { useState } from "react"
import { motion, useReducedMotion } from "framer-motion"

export type Mood = "happy" | "normal" | "sad"

interface CatCompanionProps {
  mood: Mood
  className?: string
}

/**
 * DIDA's full-body companion: a sitting cat. Its tail sways idly and
 * hovering it makes it wipe its face with its paw. Positioning lives
 * with the parent (drag anywhere, tap the wrapper to switch corners).
 * Face follows `mood`: happy while thinking or after lots of good
 * answers, sad when the last turn failed, normal otherwise.
 */
export function CatCompanion({ mood, className = "h-28 w-auto" }: CatCompanionProps) {
  const [grooming, setGrooming] = useState(false)
  const reduceMotion = useReducedMotion()

  function groom() {
    if (grooming || reduceMotion) return
    setGrooming(true)
    window.setTimeout(() => setGrooming(false), 2300)
  }

  return (
    <span
      onMouseEnter={groom}
      onFocus={groom}
      className={`block ${className} bg-transparent p-0`}
    >
      <svg viewBox="0 0 120 150" fill="none" className="h-full w-full drop-shadow-lg">
        {/* tail (behind body) */}
        <motion.g
          style={{ transformOrigin: "92px 128px" }}
          animate={reduceMotion ? undefined : { rotate: [-9, 11, -9] }}
          transition={reduceMotion ? undefined : { duration: 3.6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        >
          <path
            d="M92 128C112 126 122 112 118 96c-2-10-10-16-18-14"
            stroke="#55555f"
            strokeWidth="9"
            strokeLinecap="round"
          />
          <path d="M116 90c1-4 0-7-2-9l5 1c1 3 0 6-3 8Z" fill="#D71921" />
        </motion.g>

        {/* body */}
        <ellipse cx="58" cy="108" rx="30" ry="32" fill="#55555f" />
        <ellipse cx="58" cy="114" rx="17" ry="22" fill="#676672" />
        <ellipse cx="34" cy="136" rx="12" ry="6" fill="#4a4a54" />
        {/* back stripes */}
        <path d="M36 92l-6 2M34 104l-6 2M82 92l6 2" stroke="#3a3a45" strokeWidth="2.5" strokeLinecap="round" />
        {/* left front leg (static) */}
        <rect x="46" y="104" width="9" height="30" rx="4.5" fill="#4a4a54" />

        {/* head (tilts a little while grooming) */}
        <motion.g
          style={{ transformOrigin: "58px 62px" }}
          animate={grooming ? { rotate: [0, 7, 2, 7, 0] } : { rotate: 0 }}
          transition={grooming ? { duration: 2.2, ease: "easeInOut" } : { duration: 0.3 }}
        >
          {/* ears */}
          <path d="M42 30 36 10l16 10-10 10Z" fill="#55555f" />
          <path d="M43 24.5 40.5 16l7.5 4.5-5 4Z" fill="#D71921" />
          <path d="M74 30l6-20-16 10 10 10Z" fill="#55555f" />
          <path d="M73 24.5l2.5-8.5-7.5 4.5 5 4Z" fill="#D71921" />
          {/* head */}
          <circle cx="58" cy="42" r="21" fill="#55555f" />
          {/* forehead stripes */}
          <path d="M50 24.5 49 30M58 23v6M66 24.5l1 5.5" stroke="#3a3a45" strokeWidth="2" strokeLinecap="round" />
          {/* eyes */}
          {mood === "happy" ? (
            <>
              <path d="M45.5 42c1.2-2 3.4-2 4.6 0" stroke="#101014" strokeWidth="2" strokeLinecap="round" />
              <path d="M65.9 42c1.2-2 3.4-2 4.6 0" stroke="#101014" strokeWidth="2" strokeLinecap="round" />
            </>
          ) : (
            <>
              <circle cx="48" cy="41" r="2" fill="#101014" />
              <circle cx="68" cy="41" r="2" fill="#101014" />
            </>
          )}
          {/* blush when happy */}
          {mood === "happy" && (
            <>
              <ellipse cx="43" cy="47" rx="2.8" ry="1.7" fill="#e06565" opacity="0.7" />
              <ellipse cx="73" cy="47" rx="2.8" ry="1.7" fill="#e06565" opacity="0.7" />
            </>
          )}
          {/* nose + mouth */}
          <path d="M56 48.5h4l-2 2.4-2-2.4Z" fill="#D71921" />
          {mood === "happy" && (
            <path
              d="M58 51v2.4M58 53.4c-1.2 2-3.6 2.2-5 .8M58 53.4c1.2 2 3.6 2.2 5 .8"
              stroke="#101014"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          )}
          {mood === "normal" && (
            <path
              d="M58 51.5v1.5M58 53c-1 1.2-2.6 1.2-3.6.4M58 53c1 1.2 2.6 1.2 3.6.4"
              stroke="#101014"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          )}
          {mood === "sad" && (
            <>
              <path d="M54 56.5c1.8-2.6 6.2-2.6 8 0" stroke="#101014" strokeWidth="1.8" strokeLinecap="round" />
              <path d="M75 44c1.4 2.2 1.4 4.2 0 5.2-1.4-1-1.4-3 0-5.2Z" fill="#7cc4f4" />
            </>
          )}
          {/* whiskers */}
          <path d="M32 46l-9-1M32.5 50l-8 2M84 46l9-1M83.5 50l8 2" stroke="#33333c" strokeWidth="1.2" strokeLinecap="round" />
        </motion.g>

        {/* collar */}
        <path d="M38 62Q58 72 78 62" stroke="#D71921" strokeWidth="5" strokeLinecap="round" />
        <circle cx="58" cy="69.5" r="3.4" fill="#f5c542" />

        {/* right front paw: rests down, wipes the face when poked */}
        <motion.g
          style={{ transformOrigin: "66px 106px" }}
          animate={
            grooming
              ? { rotate: [0, -62, -34, -62, -34, 0], x: [0, 8, 3, 8, 3, 0], y: [0, -24, -13, -24, -13, 0] }
              : { rotate: 0, x: 0, y: 0 }
          }
          transition={grooming ? { duration: 2.2, ease: "easeInOut" } : { duration: 0.25 }}
        >
          <rect x="62" y="104" width="9" height="30" rx="4.5" fill="#4a4a54" />
          <circle cx="66.5" cy="136" r="6" fill="#5d5d68" />
        </motion.g>
      </svg>
    </span>
  )
}
