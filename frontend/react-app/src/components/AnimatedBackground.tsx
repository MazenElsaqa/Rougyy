import { motion } from "framer-motion"

// Animated backdrop adapted from the "Background Paths" hero concept:
// the same flowing-paths idea, restyled to the app theme (primary
// teal at low opacity) and rendered as a non-interactive layer behind
// the chat UI. No shadcn dependency -- background only, the app keeps
// its own header/sidebar/composer.
const PATH_COUNT = 28

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

function FloatingPaths({ position, seedOffset = 0 }: { position: number; seedOffset?: number }) {
  const paths = Array.from({ length: PATH_COUNT }, (_, i) => ({
    id: i,
    d: pathDefinition(i, position),
    width: 0.5 + i * 0.03,
    // Deterministic durations (no Math.random in render) so StrictMode
    // double-renders and re-renders stay visually stable.
    duration: 22 + ((i * 7 + seedOffset) % 11),
  }))

  return (
    <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
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
            animate={{
              pathLength: 1,
              opacity: [0.3, 0.6, 0.3],
              pathOffset: [0, 1, 0],
            }}
            transition={{
              duration: path.duration,
              repeat: Number.POSITIVE_INFINITY,
              ease: "linear",
            }}
          />
        ))}
      </svg>
    </div>
  )
}

export function AnimatedBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden motion-reduce:hidden" aria-hidden="true">
      {/* Soft brand-tinted wash so the paths sit on theme, plus a bottom
          fade into the background color for readability of the composer. */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary-muted/60 via-transparent to-background" />
      <FloatingPaths position={1} />
      <FloatingPaths position={-1} seedOffset={5} />
    </div>
  )
}
