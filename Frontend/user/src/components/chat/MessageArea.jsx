import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import MessageBubble from './MessageBubble'
import PulseWave from '../fx/PulseWave'
import { springs } from '../fx/springs'

export default function MessageArea({ conversation, messages, currentUserId, onSend, socketConnected, loading, firstUnreadMessageId, unreadCount, aiBusy = false }) {
  const [draft, setDraft] = useState('')
  const scrollRef = useRef(null)
  const [unreadDismissed, setUnreadDismissed] = useState(false)

  useEffect(() => { scrollRef.current?.scrollIntoView({ block: 'end' }) }, [messages])
  // New unread marker (new conversation, or same conversation reopened) - show the button again.
  useEffect(() => { setUnreadDismissed(false) }, [firstUnreadMessageId])

  const submit = (e) => {
    e.preventDefault()
    if (!draft.trim() || !socketConnected) return
    if (onSend(draft.trim())) setDraft('')
  }

  // Only true when the marked message is actually among the currently loaded ones - useMessages
  // sizes its initial fetch to cover the known unread backlog, but in the rare case a backlog is
  // larger than the backend's page cap, the target may not be loaded; hide the button rather than
  // show one that silently does nothing on click.
  const unreadTargetLoaded = firstUnreadMessageId && messages.some(m => m.id === firstUnreadMessageId)

  const jumpToUnread = () => {
    document.getElementById(`msg-${firstUnreadMessageId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setUnreadDismissed(true)
  }

  return (
    // Faint dot-matrix texture on the central canvas (pillar 1) - a Tailwind arbitrary
    // background-image so the panel doesn't read as an empty flat void, kept subtle (2% opacity
    // dots) so it never competes with the actual messages on top of it.
    <div className="message-area bg-[radial-gradient(circle,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[length:22px_22px]">
      {unreadTargetLoaded && !unreadDismissed && (
        <button type="button" className="jump-to-unread-btn" onClick={jumpToUnread}>
          <i className="bi bi-arrow-up" /> {unreadCount} tin nhắn mới
        </button>
      )}
      <div className="messages-scroll">
        <div className="date-divider"><span>Today</span></div>
        {loading && <p className="text-muted small text-center mt-3">Đang tải tin nhắn...</p>}
        <AnimatePresence initial={false}>
          {!loading && messages.map(m => (
            // Pillar 4: message overshoot entrance - slides up and slightly overshoots before
            // settling, spring-driven (never linear easing).
            <motion.div
              key={m.id} id={`msg-${m.id}`} layout
              initial={{ opacity: 0, y: 18, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={springs.messageEnter}
            >
              {m.id === firstUnreadMessageId && <div className="unread-divider"><span>{unreadCount} tin nhắn mới</span></div>}
              <MessageBubble message={m} own={m.sender_id === currentUserId} />
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={scrollRef} />
      </div>
      <form className="composer" onSubmit={submit}>
        <div className="composer-main"><input value={draft} onChange={e => setDraft(e.target.value)} placeholder={socketConnected ? `Message ${conversation.name}...` : 'Connecting to chat...'} /><button className="send-btn" aria-label="Send" disabled={!socketConnected || !draft.trim()}><i className="bi bi-send-fill" /></button></div>
        <PulseWave active={aiBusy} />
        <div className="composer-help"><span><i className="bi bi-stars" /> Type <strong>@orbit</strong> to ask AI</span><span>{socketConnected ? 'Enter to send' : 'Reconnecting…'}</span></div>
      </form>
    </div>
  )
}
