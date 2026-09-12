import { memo, useMemo } from "react"
import { motion } from "framer-motion"

const PATH_COUNT = 24

function pathDefinition(index: number, _position: number, seedOffset: number): string {
  // U-shaped valley: lines enter from the upper-left, sweep DOWN to a
  // trough along the bottom, then curve like a wave and rise back UP to
  // the top-right. The upper-middle of the screen stays empty; only the
  // edges and the bottom band carry lines.
  const startY = 45 + ((index * 11 + seedOffset * 29) % 110)
  const trough = 325 + ((index * 7 + seedOffset * 13) % 30)
  const exitY = 50 + ((index * 5 + seedOffset * 17) % 45)
  return (
    `M-60 ${startY}` +
    `C60 ${startY + 30} 130 ${startY + 140} 210 300` +
    `C280 ${trough + 10} 370 ${trough + 12} 450 ${trough - 8}` +
    `C530 ${trough - 30} 560 220 610 150` +
    `C650 100 690 70 745 ${exitY}`
  )
}

const FloatingPaths = memo(function FloatingPaths({ position, seedOffset = 0 }: { position: number; seedOffset?: number }) {
  const paths = useMemo(
    () =>
      Array.from({ length: PATH_COUNT }, (_, i) => ({
        id: i,
        d: pathDefinition(i, position, seedOffset),
        width: 0.6 + i * 0.03,
        duration: 22 + ((i * 7 + seedOffset) % 11),
      })),
    [position, seedOffset],
  )

  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <svg
        className="h-full w-full text-primary"
        viewBox="0 0 696 316"
        fill="none"
        preserveAspectRatio="xMidYMid slice"
      >
        <title>Background Paths</title>
        {paths.map((path) => (
          <motion.path
            key={path.id}
            d={path.d}
            stroke="currentColor"
            strokeWidth={path.width}
            strokeOpacity={0.1 + path.id * 0.015}
            initial={{ pathLength: 0.3, opacity: 0.7 }}
            animate={{ pathLength: 1, opacity: [0.4, 0.85, 0.4], pathOffset: [0, 1, 0] }}
            transition={{ duration: path.duration, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
          />
        ))}
      </svg>
    </div>
  )
})

export const AnimatedBackground = memo(function AnimatedBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden motion-reduce:hidden" aria-hidden="true">
      {/* Light wash plus red radial glows so the drawing lines read clearly. */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary-muted/30 via-transparent to-background" />
      <div className="absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-primary/15 blur-3xl" />
      <div className="absolute -right-32 bottom-1/4 h-96 w-96 rounded-full bg-primary/15 blur-3xl" />
      <FloatingPaths position={1} />
      <FloatingPaths position={-1} seedOffset={5} />
    </div>
  )
})
