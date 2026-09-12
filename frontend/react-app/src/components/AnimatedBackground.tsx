import { memo, useMemo } from "react"
import { motion } from "framer-motion"

const PATH_COUNT = 16

function pathDefinition(index: number, seedOffset: number): string {
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

const FloatingPaths = memo(function FloatingPaths({ seedOffset = 0 }: { seedOffset?: number }) {
  const paths = useMemo(
    () =>
      Array.from({ length: PATH_COUNT }, (_, i) => ({
        id: i,
        d: pathDefinition(i, seedOffset),
        width: 0.7 + i * 0.04,
        drawDelay: (i % 8) * 0.15,
      })),
    [seedOffset],
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
            strokeOpacity={0.14 + path.id * 0.018}
            // Draw-once on mount only. The old infinite pathLength /
            // pathOffset loop re-rasterized a full-screen SVG every frame
            // (not GPU-composited) and, combined with the backdrop-blur
            // glass panels sampling it, produced the visible flicker.
            initial={{ pathLength: 0.25, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 2.4, delay: path.drawDelay, ease: "easeOut" }}
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
      {/* Perpetual motion lives here now: whole layers drifting via
          GPU-composited transforms (translate3d/opacity only), which the
          compositor handles without repainting the SVG or the blur. */}
      <div className="bg-drift-a absolute inset-[-4%] will-change-transform">
        <FloatingPaths seedOffset={0} />
      </div>
      <div className="bg-drift-b absolute inset-[-4%] will-change-transform">
        <FloatingPaths seedOffset={5} />
      </div>
    </div>
  )
})
