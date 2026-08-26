import { useEffect, useRef } from 'react'
import gsap from 'gsap'

// Thin wrapper around gsap.context() - scopes tween selectors to a ref's subtree and guarantees
// every tween/timeline created inside `setup` is killed on unmount or when `active` flips false,
// so GSAP never leaks a running tween into an unmounted/hidden component. GSAP's own role in this
// app is intentionally narrow (ScanningBorder, PulseWave) - this hook is the one place that owns
// its lifecycle, so neither component has to hand-roll context creation/cleanup.
export function useGsapContext(setup, { active = true, deps = [] } = {}) {
  const scopeRef = useRef(null)

  useEffect(() => {
    if (!active || !scopeRef.current) return undefined
    const ctx = gsap.context(setup, scopeRef)
    return () => ctx.revert()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, ...deps])

  return scopeRef
}
