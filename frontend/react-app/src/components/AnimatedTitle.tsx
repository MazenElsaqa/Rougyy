import { motion } from "framer-motion"

/**
 * Letter-by-letter spring title for the empty state, adapted from the
 * "Background Paths" hero: same staggered spring idea, restyled to the
 * app theme (foreground->muted gradient instead of neutral-900).
 */
export function AnimatedTitle({ text }: { text: string }) {
  const words = text.split(" ")

  return (
    <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl" aria-label={text}>
      {words.map((word, wordIndex) => (
        <span key={wordIndex} className="mr-3 inline-block last:mr-0" aria-hidden="true">
          {word.split("").map((letter, letterIndex) => (
            <motion.span
              key={`${wordIndex}-${letterIndex}`}
              initial={{ y: 60, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{
                delay: wordIndex * 0.08 + letterIndex * 0.025,
                type: "spring",
                stiffness: 180,
                damping: 26,
              }}
              className="inline-block bg-gradient-to-r from-foreground to-muted bg-clip-text text-transparent"
            >
              {letter}
            </motion.span>
          ))}
        </span>
      ))}
    </h2>
  )
}
