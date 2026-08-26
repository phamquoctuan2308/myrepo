import { motion } from 'framer-motion'
import { springs } from './springs'

// Pillar 1: Z-axis "hologram" bloom-in. A plain mount animation (initial -> animate) on the root of
// a page that genuinely remounts on route entry (ChatPage/PersonalAssistantPage/TaskInboxPage) -
// deliberately NOT wrapped in AnimatePresence/a global route transition, since that would require
// keeping the *outgoing* page's DOM alive across a navigation, which means moving AppRouter's whole
// route table into AppLayout (below the single shared WebSocket) to avoid remounting the socket on
// every nav. That's a larger structural change than this PR takes on - see TransitionVeil for the
// complementary "outgoing" half of the effect.
export default function HologramSurface({ children, className = '' }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, scale: 0.95, filter: 'blur(10px)' }}
      animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
      transition={springs.surfaceOpen}
    >
      {children}
    </motion.div>
  )
}
