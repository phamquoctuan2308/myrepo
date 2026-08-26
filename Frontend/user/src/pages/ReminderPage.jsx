import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import PageHeader from '../components/common/PageHeader'
import NewReminderModal from '../components/reminder/NewReminderModal'
import { useAuth } from '../context/AuthContext'
import { useWorkspace } from '../context/WorkspaceContext'
import { listReminders, cancelReminder } from '../api/reminders'
import { getColor } from '../utils/avatar'
import { formatDateTime } from '../utils/datetime'

const statusLabel = { scheduled: 'Scheduled', fired: 'Fired', cancelled: 'Cancelled' }
const statusClass = { scheduled: 'primary', fired: 'success', cancelled: 'secondary' }

export default function ReminderPage() {
  const { token } = useAuth()
  const { workspaceId } = useWorkspace()
  const { subscribe } = useOutletContext()
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [newOpen, setNewOpen] = useState(false)
  const [error, setError] = useState('')

  const refresh = () => {
    setLoading(true)
    setError('')
    if (!token || !workspaceId) {
      setReminders([])
      setLoading(false)
      return
    }
    listReminders(token, workspaceId).then(setReminders).catch(err => setError(err.detail || 'Could not load reminders.')).finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [token, workspaceId])

  const upsertReminder = (reminder) => setReminders(prev => [...prev.filter(r => r.id !== reminder.id), reminder])

  // Realtime: a reminder can be created from this page's own "New reminder", another tab, the
  // agent's create_reminder tool, or auto-created behind an Accepted proactive task - same
  // upsert-on-push pattern CalendarPage.jsx uses for calendar_event_* so every open tab agrees.
  useEffect(() => subscribe((data) => {
    if (data.type !== 'reminder_fired') return
    if (data.reminder.workspace_id !== workspaceId) return
    setReminders(prev => prev.map(r => r.id === data.reminder.id ? { ...r, status: 'fired' } : r))
  }), [subscribe, workspaceId])

  const onCreated = (reminder) => setReminders(prev => [...prev, reminder])
  const onCancel = (reminder) => cancelReminder(token, reminder.id, workspaceId).then(refresh).catch(err => setError(err.detail || 'Could not cancel reminder.'))

  return <div className="page-container">
    <PageHeader eyebrow="Stay focused" title="Reminders" description="Gentle nudges for everything that matters." action={<button className="btn btn-primary" onClick={() => setNewOpen(true)}><i className="bi bi-plus-lg me-2"/>New reminder</button>}/>
    {error && <div className="auth-error mb-3">{error}</div>}
    <div className="reminder-layout"><section className="content-card reminder-list"><div className="card-toolbar"><div><h3>Upcoming reminders</h3><span>{reminders.filter(r => r.status === 'scheduled').length} active reminders</span></div></div>
      {loading ? <p className="text-muted small p-3 mb-0">Loading...</p> : reminders.map(r => (
        <div className={`reminder-row ${r.status !== 'scheduled' ? 'disabled' : ''}`} key={r.id}>
          <div className="reminder-icon" style={{ background: `${getColor(r.id)}12`, color: getColor(r.id) }}><i className="bi bi-alarm"/></div>
          <div className="reminder-info"><h4>{r.title}</h4><strong>{formatDateTime(r.due_at)}</strong><div><span><i className="bi bi-bell"/>Reminds at {formatDateTime(r.fire_at)}</span>{r.message && <span><i className="bi bi-chat-left-text"/>{r.message}</span>}</div></div>
          <div className="reminder-controls"><span className={`status-badge ${statusClass[r.status]}`}>{statusLabel[r.status]}</span>{r.status === 'scheduled' && <button className="btn btn-sm btn-light" onClick={() => onCancel(r)}>Cancel</button>}</div>
        </div>
      ))}
      {!loading && !reminders.length && <p className="text-muted small p-3 mb-0">No reminders yet.</p>}
    </section>
      <aside><div className="notification-preview"><div className="preview-label"><span>Preview</span><i className="bi bi-phone"/></div><div className="phone-notification"><div className="orbit-mini"><i className="bi bi-command"/></div><div><div><strong>Orbit</strong><time>now</time></div><h4>Product launch call</h4><p>Starting in 30 minutes • Product Launch</p></div></div><div className="preview-glow"/></div><div className="reminder-tip"><i className="bi bi-lightbulb"/><div><strong>Realtime</strong><p>Khi reminder đến giờ, bạn sẽ thấy thông báo hiện ngay dù đang ở trang khác.</p></div></div></aside>
    </div>
    <NewReminderModal open={newOpen} onClose={() => setNewOpen(false)} onCreated={onCreated} workspaceId={workspaceId} />
  </div>
}
