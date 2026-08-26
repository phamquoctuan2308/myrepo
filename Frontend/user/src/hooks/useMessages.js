import { useEffect, useState } from 'react'
import { getMessages } from '../api/chat'

// `unreadHint` is a snapshot of the conversation's unread_count, taken by the caller BEFORE it
// gets zeroed locally on open - see ChatPage.jsx's onSelect. It only sizes the initial fetch (see
// below); it is NOT a dependency of the effect, so a later unrelated bump to the conversation list
// doesn't re-trigger a refetch/reset of the divider mid-read.
export function useMessages(token, conversationId, unreadHint = 0) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [firstUnreadMessageId, setFirstUnreadMessageId] = useState(null)
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    // Clear immediately on every conversationId change - otherwise the previous conversation's
    // messages (and unread marker) stay on screen until the new fetch resolves.
    setMessages([])
    setFirstUnreadMessageId(null)
    setUnreadCount(0)
    if (!token || !conversationId) return
    setLoading(true)
    // Fetch enough history to actually cover the known unread backlog (capped at the backend's
    // max page size, 200) - the default 50-message page could otherwise miss the first unread
    // message entirely in a long conversation with a big backlog.
    const limit = Math.min(200, Math.max(50, unreadHint + 10))
    getMessages(token, conversationId, { limit }).then(data => {
      setMessages(data.messages)
      setFirstUnreadMessageId(data.first_unread_message_id)
      setUnreadCount(unreadHint)
    }).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- unreadHint deliberately excluded, see comment above
  }, [token, conversationId])

  return { messages, setMessages, loading, firstUnreadMessageId, unreadCount }
}
