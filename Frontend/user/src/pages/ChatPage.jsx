import { useEffect, useRef, useState } from 'react'
import { useLocation, useOutletContext } from 'react-router-dom'
import ConversationList from '../components/chat/ConversationList'
import ConversationHeader from '../components/chat/ConversationHeader'
import MessageArea from '../components/chat/MessageArea'
import AIPanel from '../components/chat/AIPanel'
import NewConversationModal from '../components/chat/NewConversationModal'
import HologramSurface from '../components/fx/HologramSurface'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConversations } from '../hooks/useConversations'
import { useMessages } from '../hooks/useMessages'
import { getAiPermission, hideConversation, leaveConversation, markRead, setAiPermission, setGroupAiPolicy } from '../api/chat'
import { useWorkspace } from '../context/WorkspaceContext'

export default function ChatPage() {
  const { token, user } = useAuth()
  const { pushToast } = useToast()
  const { workspaceId } = useWorkspace()
  const location = useLocation()
  const { sendJson, socketConnected, subscribe } = useOutletContext()
  const [mobileChat, setMobileChat] = useState(false)
  const [aiOpen, setAiOpen] = useState(false)
  // Threaded down to MessageArea's PulseWave (pillar 3) so the composer's "AI active" glow reflects
  // AIPanel's real in-flight state, not a fake/local signal.
  const [aiBusy, setAiBusy] = useState(false)
  const [newConvoOpen, setNewConvoOpen] = useState(false)
  const [selectedId, setSelectedId] = useState(() => location.state?.conversationId || null)
  const [aiGranted, setAiGranted] = useState(false)
  const [aiContributionAllowed, setAiContributionAllowed] = useState(false)
  const [aiMode, setAiMode] = useState('individual')
  const [canManageAi, setCanManageAi] = useState(false)
  const [unreadHint, setUnreadHint] = useState(0)
  const { conversations, setConversations } = useConversations(token, workspaceId)
  const { messages, setMessages, loading: messagesLoading, firstUnreadMessageId, unreadCount } = useMessages(token, selectedId, unreadHint)

  // AI permission is per (conversation, user) on the backend - shared here so the header badge
  // and the AI panel's Grant/Revoke buttons always agree, instead of each fetching/toggling it
  // independently.
  useEffect(() => {
    if (!selectedId) { setAiGranted(false); setAiContributionAllowed(false); setAiMode('individual'); setCanManageAi(false); return }
    let cancelled = false
    getAiPermission(token, selectedId).then(res => {
      if (!cancelled) {
        setAiGranted(res.granted)
        setAiContributionAllowed(res.contribution_allowed)
        setAiMode(res.mode || 'individual')
        setCanManageAi(Boolean(res.can_manage))
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [selectedId, token])

  const toggleAiPermission = (id, next) => {
    const conversation = conversations.find(item => item.id === id)
    const update = conversation?.type === 'group'
      ? setGroupAiPolicy(token, id, next)
      : setAiPermission(token, id, { granted: next })
    return update.then(res => {
      setConversations(prev => prev.map(item => item.id === id ? {
        ...item,
        ai_permission_granted: res.granted,
        ...(res.mode === 'group_managed' ? { ai_enabled: res.granted } : {}),
      } : item))
      if (id === selectedId) {
        setAiGranted(res.granted)
        setAiContributionAllowed(res.contribution_allowed)
        setAiMode(res.mode || 'individual')
        setCanManageAi(Boolean(res.can_manage))
      }
      return res
    })
  }

  const onToggleAi = (next) => toggleAiPermission(selectedId, next)
  const onToggleAiInList = (id, next) =>
    toggleAiPermission(id, next).catch(error => pushToast(error.detail || 'Không thể cập nhật quyền AI.'))

  const onToggleContribution = (next) =>
    setAiPermission(token, selectedId, { contribution_allowed: next }).then(res => {
      setAiGranted(res.granted)
      setAiContributionAllowed(res.contribution_allowed)
      return res
    })

  const stateRef = useRef({ selectedId, userId: user?.id })
  stateRef.current = { selectedId, userId: user?.id }

  useEffect(() => {
    setSelectedId(null)
    setMessages([])
    setMobileChat(false)
    setAiOpen(false)
    setUnreadHint(0)
  }, [workspaceId, setMessages])

  useEffect(() => {
    if (location.state?.conversationId) {
      setSelectedId(location.state.conversationId)
      setMobileChat(true)
    }
  }, [location.state?.conversationId])

  useEffect(() => {
    if (!conversations.length) return
    if (selectedId && conversations.some(conversation => conversation.id === selectedId)) return

    const fallbackId = conversations[0].id
    setSelectedId(fallbackId)
    setUnreadHint(conversations[0].unread_count || 0)
    setConversations(prev => prev.map(c => c.id === fallbackId ? { ...c, unread_count: 0 } : c))
  }, [conversations, selectedId, setConversations])

  useEffect(() => subscribe((data) => {
    if (data.type === 'group_ai_policy_changed') {
      setConversations(prev => prev.map(c => c.id === data.conversation_id ? { ...c, ai_enabled: data.enabled } : c))
      if (data.conversation_id === stateRef.current.selectedId) {
        setAiGranted(data.enabled)
        setAiContributionAllowed(data.enabled)
      }
      return
    }
    if (data.type === 'conversation_member_left') {
      setConversations(prev => prev.map(conversation => conversation.id === data.conversation_id
        ? { ...conversation, participants: conversation.participants.filter(participant => participant.id !== data.user_id) }
        : conversation))
      return
    }
    if (data.type !== 'new_message') return
    const { selectedId, userId } = stateRef.current
    const msg = data.message
    if (msg.conversation_id === selectedId) setMessages(prev => [...prev, msg])
    setConversations(prev => {
      const idx = prev.findIndex(c => c.id === msg.conversation_id)
      if (idx === -1) return prev
      const bumpUnread = msg.conversation_id !== selectedId && msg.sender_id !== userId
      const updated = { ...prev[idx], last_message: msg, updated_at: msg.created_at, unread_count: bumpUnread ? (prev[idx].unread_count || 0) + 1 : prev[idx].unread_count }
      return [updated, ...prev.slice(0, idx), ...prev.slice(idx + 1)]
    })
  }), [subscribe, setMessages, setConversations])

  const selectedConversation = conversations.find(c => c.id === selectedId) || null

  const onSelect = (id) => {
    setSelectedId(id)
    setMobileChat(true)
    setUnreadHint(conversations.find(conversation => conversation.id === id)?.unread_count || 0)
    setConversations(prev => prev.map(c => c.id === id ? { ...c, unread_count: 0 } : c))
  }

  const markedReadRef = useRef(null)
  useEffect(() => {
    if (!selectedId || messagesLoading || markedReadRef.current === selectedId) return
    markedReadRef.current = selectedId
    markRead(token, selectedId).catch(() => {})
  }, [selectedId, messagesLoading, token])

  const onSend = (content) => selectedId
    ? sendJson({ type: 'send_message', conversation_id: selectedId, content })
    : false

  const onCreated = (conv) => {
    setConversations(prev => [conv, ...prev.filter(c => c.id !== conv.id)])
    setSelectedId(conv.id)
    setMobileChat(true)
  }

  const removeCurrentConversation = () => {
    setConversations(previous => previous.filter(conversation => conversation.id !== selectedId))
    setSelectedId(null)
    setMessages([])
    setMobileChat(false)
  }

  const onHide = async () => {
    if (!selectedId) return
    try { await hideConversation(token, selectedId); removeCurrentConversation() }
    catch (error) { pushToast(error.detail || 'Không thể ẩn hội thoại.') }
  }

  const onLeave = async () => {
    if (!selectedId) return
    try { await leaveConversation(token, selectedId); removeCurrentConversation() }
    catch (error) { pushToast(error.detail || 'Không thể rời nhóm.') }
  }

  return (
    <HologramSurface className={`chat-layout orbit-fx ${mobileChat ? 'show-chat' : ''}`}>
      <ConversationList conversations={conversations} selectedId={selectedId} onSelect={onSelect} onNewConversation={() => setNewConvoOpen(true)} onToggleAi={onToggleAiInList} />
      <section className="conversation-pane">
        {selectedConversation ? (
          <>
            <ConversationHeader conversation={selectedConversation} onBack={() => setMobileChat(false)} onAI={() => setAiOpen(true)} onHide={onHide} onLeave={onLeave} aiGranted={aiGranted} onToggleAi={onToggleAi} aiMode={aiMode} canManageAi={canManageAi} />
            <MessageArea conversation={selectedConversation} messages={messages} currentUserId={user?.id} onSend={onSend} socketConnected={socketConnected} loading={messagesLoading} firstUnreadMessageId={firstUnreadMessageId} unreadCount={unreadCount} aiBusy={aiBusy} />
          </>
        ) : (
          <div className="chat-empty-state"><i className="bi bi-chat-dots" /><p>Select a conversation or start a new one</p></div>
        )}
      </section>
      <AIPanel
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        messages={messages}
        conversationId={selectedId}
        workspaceId={workspaceId}
        granted={aiGranted}
        contributionAllowed={aiContributionAllowed}
        onToggleGrant={onToggleAi}
        onToggleContribution={onToggleContribution}
        aiMode={aiMode}
        canManageAi={canManageAi}
        onBusyChange={setAiBusy}
      />
      <NewConversationModal open={newConvoOpen} onClose={() => setNewConvoOpen(false)} onCreated={onCreated} />
    </HologramSurface>
  )
}
