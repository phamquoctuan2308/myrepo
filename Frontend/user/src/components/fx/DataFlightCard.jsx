import { useLayoutEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { springs } from './springs'

// Pillar 2: "Data Flight" - the AI-detected task card visibly leaves the toast and travels to the
// Sidebar's Tasks icon. A manual FLIP (measure source/target rects once, animate between them via
// Framer's spring `animate`), not a `layoutId` shared-element: the toast (icon + title text + link)
// and the target (an ~18px sidebar glyph) have completely different content/aspect ratios, and
// `layoutId` would visibly squash/crop the toast's text into the icon's box mid-flight. Not GSAP
// either - a weighty, overshoot-settle point-to-point tween is exactly Framer's spring engine's
// job, and keeps this the one animation users consciously watch honestly spring-physics-driven
// (pillar 4).
export default function DataFlightCard({ sourceRef, targetRef, title, onArrive }) {
  const [rects, setRects] = useState(null)

  useLayoutEffect(() => {
    const source = sourceRef.current?.getBoundingClientRect()
    const target = targetRef.current?.getBoundingClientRect()
    if (!source || !target) { onArrive?.(); return }
    setRects({
      source,
      targetCenter: { x: target.left + target.width / 2, y: target.top + target.height / 2 },
    })
  }, [sourceRef, targetRef, onArrive])

  if (!rects) return null
  const { source, targetCenter } = rects

  return (
    <motion.div
      className="data-flight-card"
      initial={{
        position: 'fixed', top: source.top, left: source.left,
        width: source.width, height: source.height, opacity: 1, scale: 1,
      }}
      animate={{
        top: targetCenter.y - 8, left: targetCenter.x - 8,
        width: 16, height: 16, opacity: 0, scale: 0.4,
      }}
      transition={springs.flight}
      onAnimationComplete={() => onArrive?.()}
      style={{ position: 'fixed', zIndex: 1090 }}
    >
      <i className="bi bi-stars" /><span>{title}</span>
    </motion.div>
  )
}
