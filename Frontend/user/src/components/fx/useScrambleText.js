import { useEffect, useRef, useState } from 'react'
// NOTE: main.jsx wraps the app in <React.StrictMode>, which double-invokes every effect once in
// dev (mount -> cleanup -> mount again) specifically to surface bugs like the one this file used
// to have: a `startedForRef` guard meant to block *replaying* the animation on an unrelated
// re-render instead survived the StrictMode cleanup (refs aren't reset by it) and silently
// blocked the second, real mount from ever starting the animation at all - the result card would
// render and then sit frozen on its first frame forever (blank before the fix below that added an
// initial scrambled buffer, visibly stuck-garbled after it). Removed - the effect's own dependency
// array is already the correct "only run when the target text actually changes" guard; nothing
// extra is needed, and per-mount identity isn't a signal `useEffect` deps can see anyway.

const DEFAULT_CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#*<>/&%'

// A fully-scrambled string the same shape as `text` (whitespace preserved, everything else
// replaced) - used as the buffer's *initial* value so the very first paint never shows an empty
// box. requestAnimationFrame doesn't fire the first tick synchronously (and browsers throttle rAF
// hard in a backgrounded/unfocused tab - e.g. right after a screenshot tool briefly steals focus),
// so starting from '' left a real window where the result card rendered with a title and no body
// at all until the next frame got a chance to run.
function scrambleShape(text, charset) {
  let out = ''
  for (let i = 0; i < text.length; i++) {
    out += /\s/.test(text[i]) ? text[i] : charset[(Math.random() * charset.length) | 0]
  }
  return out
}

// Matrix-style "decoding" text reveal (pillar 3: "Decoding Text/Scramble"). Operates on a raw
// string buffer, NOT rendered DOM - Markdown.jsx/ReactMarkdown expose no char-level nodes to
// animate in place, so this produces a plain scrambled string for a caller (ScrambledMarkdown) to
// show as-is, then swap for the real <Markdown> render once `done` flips true.
//
// Runs over a FIXED total duration regardless of text length, so a long AI summary doesn't take
// forever to "type" - only the reveal rate (chars/frame) scales with length.
export function useScrambleText(targetText, { active = false, durationMs = 700, charset = DEFAULT_CHARSET } = {}) {
  const [buffer, setBuffer] = useState(() => (active && targetText ? scrambleShape(targetText, charset) : targetText))
  const [done, setDone] = useState(!active)
  const frameRef = useRef(null)

  useEffect(() => {
    if (!active || !targetText) {
      setBuffer(targetText || '')
      setDone(true)
      return undefined
    }

    const length = targetText.length
    const totalFrames = Math.max(1, Math.round(durationMs / 16))
    const charsPerTick = Math.max(1, Math.ceil(length / totalFrames))
    let revealed = 0
    setDone(false)

    const tick = () => {
      revealed = Math.min(length, revealed + charsPerTick)
      let next = targetText.slice(0, revealed)
      for (let i = revealed; i < length; i++) {
        // Never scramble whitespace/newlines - keeps word/line shape recognizable while it decodes.
        next += /\s/.test(targetText[i]) ? targetText[i] : charset[(Math.random() * charset.length) | 0]
      }
      setBuffer(next)
      if (revealed >= length) {
        setDone(true)
        return
      }
      frameRef.current = requestAnimationFrame(tick)
    }
    frameRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameRef.current)
  }, [targetText, active, durationMs, charset])

  return { text: buffer, done }
}
