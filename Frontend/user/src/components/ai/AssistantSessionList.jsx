import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { listAssistantThreads } from '../../api/assistant'
import { formatDateShort, formatClock } from '../../utils/datetime'

const formatThreadTime = (iso) => {
  if (!iso) return ''
  const sameDay = new Date(iso).toDateString() === new Date().toDateString()
  return sameDay ? formatClock(iso) : formatDateShort(iso)
}

export default function AssistantSessionList({ activeThreadId, onSelectThread, onNewThread, refreshSignal, workspaceId }) {
  const { token } = useAuth()
  const [search, setSearch] = useState('')
  const [threads, setThreads] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token || !workspaceId) {
      setThreads([])
      setLoading(false)
      return
    }
    setLoading(true)
    listAssistantThreads(token, workspaceId).then(setThreads).catch(() => setThreads([])).finally(() => setLoading(false))
  }, [token, workspaceId, refreshSignal])

  const visible = threads.filter(t => t.title.toLowerCase().includes(search.toLowerCase()))

  return <aside className="assistant-sessions">
    <div className="assistant-session-head"><div><span>Personal space</span><h2>Trợ lý của tôi</h2></div><button className="icon-btn primary-soft" aria-label="Cuộc trò chuyện mới" onClick={onNewThread}><i className="bi bi-plus-lg" /></button></div>
    <div className="session-search"><i className="bi bi-search"/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Tìm cuộc trò chuyện"/></div>
    <div className="session-caption">Gần đây</div>
    <div className="session-items">
      {!loading && visible.length === 0 && <p className="session-empty">Chưa có cuộc trò chuyện nào với Trợ lý.</p>}
      {visible.map(t=><button className={`session-item ${t.thread_id===activeThreadId?'active':''}`} key={t.thread_id} onClick={()=>onSelectThread(t.thread_id)}><span className="session-item-icon"><i className="bi bi-chat-square-text"/></span><span className="session-item-copy"><strong>{t.title}</strong><small>{t.preview}</small></span><time>{formatThreadTime(t.updated_at)}</time></button>)}
    </div>
    <div className="assistant-private"><i className="bi bi-shield-check"/><div><strong>Không gian riêng tư</strong><small>Chỉ bạn có thể xem nội dung tại đây.</small></div></div>
  </aside>
}
