import { motion } from 'framer-motion'

/* "Active empty state" (pillar 3 of the sci-fi overhaul): replaces the plain gray-icon-and-text
   empty states scattered across Tasks/Memory/Workspaces with a small Framer Motion animation that
   reads as "AI is actively standing by and ready to process", not "there is nothing here".

   Pure Tailwind + Framer Motion, self-contained (no CSS file dependency) so it can drop into any
   page. `variant` picks the animation; `icon` is a Bootstrap Icons class (the project already
   loads bootstrap-icons everywhere, see main.jsx). */
export default function EmptyState({ icon = 'bi-stars', title, description, variant = 'pulse', action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 px-6 py-14 text-center">
      <div className="relative flex h-20 w-20 items-center justify-center">
        {variant === 'radar' && <RadarSweep icon={icon} />}
        {variant === 'pulse' && <PulseRing icon={icon} />}
        {variant === 'float' && <FloatingIcon icon={icon} />}
      </div>
      {title && <p className="m-0 text-[13px] font-bold text-orbit-ink">{title}</p>}
      {description && <p className="m-0 max-w-[360px] text-[11px] leading-relaxed text-orbit-muted">{description}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

function RadarSweep({ icon }) {
  return (
    <>
      <div className="absolute inset-0 rounded-full border border-orbit-glow-a/25" />
      <div className="absolute inset-[10px] rounded-full border border-orbit-glow-a/15" />
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: 'conic-gradient(from 0deg, rgba(82,111,245,0.55), rgba(82,111,245,0) 30%)',
          maskImage: 'radial-gradient(circle, transparent 55%, black 56%)',
          WebkitMaskImage: 'radial-gradient(circle, transparent 55%, black 56%)',
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 2.4, repeat: Infinity, ease: 'linear' }}
      />
      <i className={`bi ${icon} relative z-10 text-2xl text-orbit-glow-a`} />
    </>
  )
}

function PulseRing({ icon }) {
  return (
    <>
      {[0, 0.6, 1.2].map(delay => (
        <motion.span
          key={delay}
          className="absolute inset-0 rounded-full border border-orbit-glow-a/40"
          initial={{ opacity: 0.6, scale: 0.6 }}
          animate={{ opacity: 0, scale: 1.6 }}
          transition={{ duration: 1.8, repeat: Infinity, delay, ease: 'easeOut' }}
        />
      ))}
      <div className="relative z-10 flex h-11 w-11 items-center justify-center rounded-full bg-linear-to-br from-orbit-glow-a to-orbit-glow-b shadow-orbit-glow-focus">
        <i className={`bi ${icon} text-lg text-white`} />
      </div>
    </>
  )
}

function FloatingIcon({ icon }) {
  return (
    <motion.div
      className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md shadow-orbit-glow"
      animate={{ y: [0, -8, 0] }}
      transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
    >
      <i className={`bi ${icon} text-2xl text-orbit-glow-a`} />
    </motion.div>
  )
}
