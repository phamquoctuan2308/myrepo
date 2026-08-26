import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Renders AI-generated text as real markdown (bold, lists, links) instead of showing the raw
// **/-/# syntax the model outputs verbatim. Only ever used for assistant/LLM output - never for
// content a user typed themselves (see call sites: PersonalAIChat.jsx's own messages and
// MessageBubble.jsx, human-to-human chat, both stay plain text on purpose).
// No rehype-raw - deliberately never renders raw HTML from model output, markdown syntax only.
const components = {
  p: ({ children }) => <p className="md-p">{children}</p>,
  ul: ({ children }) => <ul className="md-list">{children}</ul>,
  ol: ({ children }) => <ol className="md-list">{children}</ol>,
  li: ({ children }) => <li className="md-li">{children}</li>,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a>,
  code: ({ children }) => <code className="md-code">{children}</code>,
}

export default function Markdown({ children }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{children}</ReactMarkdown>
}
