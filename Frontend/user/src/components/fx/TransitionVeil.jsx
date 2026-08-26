import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'

// Pillar 1's "outgoing" half. True bidirectional crossfade would need the previous route's DOM
// kept alive during its own exit animation (see HologramSurface's docstring for why that's out of
// scope here) - instead, a brief frosted-glass veil masks the instant <Outlet/> swap on navigations
// into/out of an AI/chat surface, synchronized with the new page's own HologramSurface bloom-in, so
// the transition *reads* as depth without actually animating the outgoing page's pixels.
const ORBIT_ROUTES = ['/chat', '/assistant', '/tasks/inbox']
const isOrbitRoute = (pathname) => ORBIT_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`))

export default function TransitionVeil() {
  const { pathname } = useLocation()
  const previousRef = useRef(pathname)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const previous = previousRef.current
    previousRef.current = pathname
    if (previous === pathname) return undefined
    if (!isOrbitRoute(previous) && !isOrbitRoute(pathname)) return undefined
    setVisible(true)
    const timer = setTimeout(() => setVisible(false), 180)
    return () => clearTimeout(timer)
  }, [pathname])

  if (!visible) return null
  return (
    <motion.div
      className="orbit-transition-veil"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      aria-hidden="true"
    />
  )
}
