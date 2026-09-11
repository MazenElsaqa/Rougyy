import { memo, useMemo } from "react"
import { motion } from "framer-motion"

const PATH_COUNT = 10

function pathDefinition(index: number, position: number): string {
  return (
    `M-${380 - index * 5 * position} -${189 + index * 6}` +
    `C-${380 - index * 5 * position} -${189 + index * 6} ` +
    `-${312 - index * 5 * position} ${216 - index * 6} ` +
    `${152 - index * 5 * position} ${343 - index * 6}` +
    `C${616 - index * 5 * position} ${470 - index * 6} ` +
    `${684 - index * 5 * position} ${875 - index * 6} ` +
    `${684 - index * 5 * position} ${875 - index * 6}`
  )
}

const FloatingPaths = memo(function FloatingPaths({ position, seedOffset = 0 }: { position: number; seedOffset?: number }) {
  const paths = useMemo(
    () =>
      Array.from({ length: PATH_COUNT }, (_, i) => ({
        id: i,
        d: pathDefinition(i, position),
        width: 0.5 + i * 0.03,
        duration: 22 + ((i * 7 + seedOffset) % 11),
      })),
    [position, seedOffset],
  )

  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <svg className="h-full w-full text-primary" viewBox="0 0 696 316" fill="none" preserveAspectRatio="xMidYMid slice">
        <title>Background Paths</title>
        {paths.map((path) => (
          <motion.path
            key={path.id}
            d={path.d}
            stroke="currentColor"
            strokeWidth={path.width}
            strokeOpacity={0.05 + path.id * 0.012}
            initial={{ pathLength: 0.3, opacity: 0.6 }}
            animate={{ pathLength: 1, opacity: [0.3, 0.6, 0.3], pathOffset: [0, 1, 0] }}
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
      <div className="absolute inset-0 bg-gradient-to-b from-primary-muted/60 via-transparent to-background" />
      <FloatingPaths position={1} />
      <FloatingPaths position={-1} seedOffset={5} />
    </div>
  )
})
