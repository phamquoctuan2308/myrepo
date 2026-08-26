import Markdown from '../common/Markdown'
import { useScrambleText } from './useScrambleText'

// While decoding: plain monospace text buffer (never fed through ReactMarkdown - mid-scramble
// text is garbage-charset noise, not valid markdown). Once locked in: the real <Markdown>, verbatim.
export default function ScrambledMarkdown({ text, active = false, durationMs = 700 }) {
  const { text: buffer, done } = useScrambleText(text, { active, durationMs })
  if (!done) return <pre className="scramble-buffer">{buffer}</pre>
  return <Markdown>{text}</Markdown>
}
