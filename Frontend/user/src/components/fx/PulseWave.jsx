import gsap from 'gsap'
import { useGsapContext } from '../../hooks/useGsapContext'

const BAR_COUNT = 5

// Pillar 3: "subtle, organic glowing audio wave" shown while the AI is active/listening. GSAP owns
// this (not Framer): a randomized, staggered, infinite yoyo loop across several elements is
// tedious to express as static Framer variants, while it's a one-line GSAP timeline.
export default function PulseWave({ active = false }) {
  const scopeRef = useGsapContext((self) => {
    const bars = self.selector('.pulse-bar')
    gsap.timeline({ repeat: -1, yoyo: true })
      .to(bars, {
        scaleY: () => gsap.utils.random(0.35, 1.6),
        duration: 0.5,
        ease: 'sine.inOut',
        stagger: { each: 0.08, from: 'center', repeat: -1, yoyo: true },
      })
  }, { active })

  return (
    <div ref={scopeRef} className={`pulse-wave ${active ? 'active' : ''}`} aria-hidden="true">
      {Array.from({ length: BAR_COUNT }).map((_, i) => <span key={i} className="pulse-bar" />)}
    </div>
  )
}
