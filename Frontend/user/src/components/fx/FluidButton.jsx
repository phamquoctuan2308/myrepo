import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { springs } from './springs'

// Pillar 2: "Fluid Buttons" - Accept/Confirm shrinks into a pulse ring on click, then snaps
// outward into a neon-green checkmark once the action actually resolves. `onClick` is expected to
// return a Promise (or be awaitable); this component only owns the visual state machine
// (idle -> pending -> success/error), never the action itself - the caller's existing
// accept()/respondToInterrupt() logic is reused unchanged.
export default function FluidButton({ label, onClick, disabled = false, className = '' }) {
  const [status, setStatus] = useState('idle') // idle | pending | success | error

  const handleClick = async () => {
    if (status === 'pending' || status === 'success' || disabled) return
    setStatus('pending')
    try {
      await onClick()
      setStatus('success')
    } catch {
      // The caller's own onClick is responsible for surfacing the error (pushToast/setError) -
      // this just reverts the button so the user can retry.
      setStatus('idle')
    }
  }

  return (
    <motion.button
      type="button"
      layout
      transition={status === 'success' ? springs.buttonSnap : springs.buttonMorph}
      className={`fluid-button fluid-button--${status} ${className}`}
      onClick={handleClick}
      disabled={disabled || status === 'pending' || status === 'success'}
    >
      <AnimatePresence mode="wait" initial={false}>
        {status === 'idle' && (
          <motion.span key="label" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            {label}
          </motion.span>
        )}
        {status === 'pending' && (
          <motion.span
            key="ring" className="fluid-ring"
            initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
          />
        )}
        {status === 'success' && (
          <motion.span
            key="check" className="fluid-check"
            initial={{ opacity: 0, scale: 0.3, rotate: -45 }} animate={{ opacity: 1, scale: 1, rotate: 0 }}
          >
            <i className="bi bi-check-lg" />
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  )
}
