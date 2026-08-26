// Framer Motion spring presets shared by every orbit-fx animation - "heavy but responsive", never
// linear easing (see docs request: pillar 4 "Spring Physics / Natural Momentum"). Centralized here
// so every component tunes against the same physical vocabulary instead of picking ad hoc numbers.
export const springs = {
  // (a) message overshoot entrance - snappy, visible overshoot, settles fast
  messageEnter: { type: 'spring', stiffness: 500, damping: 24, mass: 0.8 },

  // (b) task-card drag - heavy, resists quick flicks, feels weighty in hand
  cardDrag: { type: 'spring', stiffness: 260, damping: 30, mass: 1.3 },

  // (c) modal / drawer / panel-bloom open
  surfaceOpen: { type: 'spring', stiffness: 340, damping: 32, mass: 1.0 },

  // (d.1) Fluid Button: pill -> pulse ring shrink (fast, decisive)
  buttonMorph: { type: 'spring', stiffness: 600, damping: 30, mass: 0.5 },
  // (d.2) Fluid Button: ring -> checkmark "snap outward" (bouncier, celebratory)
  buttonSnap: { type: 'spring', stiffness: 700, damping: 18, mass: 0.6 },

  // Data Flight - long screen-distance travel, deliberate weighty arc
  flight: { type: 'spring', stiffness: 120, damping: 18, mass: 1.4 },
}
