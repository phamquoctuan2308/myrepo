import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { useGsapContext } from '../../hooks/useGsapContext'

// Pillar 3: "glowing, laser-like thin border that continuously scans around the edges" while Orbit
// is analyzing. An absolutely-positioned SVG overlay - a pure addition, never touches the host
// container's own border/background/padding, so it composes with `.ai-panel`/`.personal-chat`
// without any changes to those rules. GSAP owns this (not Framer): a continuous, linear,
// restart/kill-controlled loop on a raw ref is exactly GSAP's strength, and it's a mechanical
// "scan" - deliberately not spring-eased, unlike every other orbit-fx animation (pillar 4's spring
// physics is reserved for UI object motion, not this instrument-panel effect).
export default function ScanningBorder({ active = false }) {
  const rootRef = useRef(null)
  const rectRef = useRef(null)
  const [box, setBox] = useState({ w: 0, h: 0 })
  const perimeter = 2 * (box.w + box.h) || 1
  const dash = Math.max(24, perimeter * 0.18)

  useEffect(() => {
    const el = rootRef.current?.parentElement
    if (!el) return undefined
    const measure = () => setBox({ w: el.clientWidth, h: el.clientHeight })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useGsapContext(() => {
    gsap.set(rectRef.current, { strokeDasharray: `${dash} ${Math.max(1, perimeter - dash)}`, strokeDashoffset: 0 })
    gsap.to(rectRef.current, { strokeDashoffset: -perimeter, duration: 2.4, ease: 'none', repeat: -1 })
  }, { active: active && box.w > 0 && box.h > 0, deps: [dash, perimeter] })

  return (
    <div ref={rootRef} className={`scanning-border ${active ? 'active' : ''}`} aria-hidden="true">
      {box.w > 0 && (
        <svg width={box.w} height={box.h} viewBox={`0 0 ${box.w} ${box.h}`}>
          <defs>
            <linearGradient id="orbit-scan-gradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--ofx-glow-a)" stopOpacity="0" />
              <stop offset="45%" stopColor="var(--ofx-glow-a)" stopOpacity="1" />
              <stop offset="100%" stopColor="var(--ofx-glow-b)" stopOpacity="0" />
            </linearGradient>
          </defs>
          <rect
            ref={rectRef}
            x="1" y="1" width={Math.max(0, box.w - 2)} height={Math.max(0, box.h - 2)}
            fill="none" stroke="url(#orbit-scan-gradient)" strokeWidth="1.5"
          />
        </svg>
      )}
    </div>
  )
}
