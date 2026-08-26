import { useState } from 'react'
import Avatar from '../common/Avatar'
import { getInitials, getColor, formatTime } from '../../utils/avatar'

export default function ConversationList({ conversations, selectedId, onSelect, onNewConversation, onToggleAi }) {
  const [search, setSearch] = useState('')
  const filtered = conversations.filter(c => c.name.toLowerCase().includes(search.toLowerCase()))
  return (
    <section className="conversation-list">
      <div className="conversation-title"><div><h2>Messages</h2><span>{conversations.length} conversations</span></div><button className="icon-btn primary-soft" onClick={onNewConversation}><i className="bi bi-pencil-square" /></button></div>
      <div className="conversation-search"><i className="bi bi-search" /><input placeholder="Search conversations" value={search} onChange={e => setSearch(e.target.value)} /></div>
      <div className="conversation-items">
        {filtered.map(c => (
          // A native <button> can't contain the checkbox toggle below (invalid nesting), so this
          // row is a div acting as a button (role/tabIndex/onKeyDown) instead - same click/keyboard
          // behavior as before, just structurally able to host the AI toggle as a sibling control.
          <div
            key={c.id}
            className={`chat-item ${c.id === selectedId ? 'active' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(c.id)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(c.id) } }}
          >
            <Avatar initials={getInitials(c.name)} color={getColor(c.id)} size={44} />
            <span className="chat-item-body">
              <span className="chat-item-top">
                <strong>{c.name}</strong>
                <span className="chat-item-top-right">
                  <time>{formatTime(c.last_message?.created_at || c.updated_at)}</time>
                  <label className="form-check form-switch chat-item-ai-toggle m-0" onClick={e => e.stopPropagation()} title={c.type === 'group' && c.my_resource_role !== 'manager' ? 'Chỉ người quản lý hội thoại có thể đổi chính sách AI của nhóm' : c.ai_permission_granted ? 'AI đang được đọc hội thoại này - bấm để tắt' : 'AI chưa được đọc hội thoại này - bấm để bật'}>
                    <input
                      className="form-check-input"
                      type="checkbox"
                      role="switch"
                      checked={!!c.ai_permission_granted}
                      disabled={c.type === 'group' && c.my_resource_role !== 'manager'}
                      onChange={e => onToggleAi(c.id, e.target.checked)}
                      aria-label={`AI ${c.ai_permission_granted ? 'đang bật' : 'đang tắt'} cho ${c.name}`}
                    />
                  </label>
                </span>
              </span>
              <span className="chat-item-bottom"><span>{c.last_message?.content || 'No messages yet'}</span>{c.unread_count > 0 && <b>{c.unread_count}</b>}</span>
            </span>
          </div>
        ))}
        {!filtered.length && <p className="text-muted small text-center mt-4">No conversations yet.</p>}
      </div>
    </section>
  )
}
