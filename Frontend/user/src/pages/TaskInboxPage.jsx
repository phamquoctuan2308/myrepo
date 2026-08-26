import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import PageHeader from '../components/common/PageHeader'
import StatCard from '../components/common/StatCard'
import { formatDue } from '../components/task/TaskTable'
import TaskConflictModal from '../components/task/TaskConflictModal'
import { useAuth } from '../context/AuthContext'
import { useWorkspace } from '../context/WorkspaceContext'
import { useToast } from '../context/ToastContext'
import { listTasks, updateTaskStatus } from '../api/tasks'
import { useTaskAccept } from '../hooks/useTaskAccept'
import { groupTasks } from '../utils/taskGrouping'
import HologramSurface from '../components/fx/HologramSurface'
import FluidButton from '../components/fx/FluidButton'

const sourceLabel = { manual: 'Manual', proactive: 'AI suggestion' }
const priorityClass = { High: 'danger', Medium: 'warning', Low: 'info' }
const ACTION_FAILED = 'Không thực hiện được, thử lại sau.'

// "Inbox nhiệm vụ ưu tiên" (đề bài, Nâng cao): a triage feed distinct from the full /tasks list -
// only what needs a decision or attention *right now*, ranked instead of just chronological.
export default function TaskInboxPage() {
  const { token } = useAuth()
  const { workspaceId } = useWorkspace()
  const { pushToast } = useToast()
  const { subscribe } = useOutletContext()
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)

  const refresh = () => {
    setLoading(true)
    if (!token || !workspaceId) {
      setTasks([])
      setLoading(false)
      return
    }
    listTasks(token, workspaceId).then(setTasks).catch(err => pushToast(err.detail || ACTION_FAILED)).finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [token, workspaceId])

  const upsertTask = (task) => setTasks(prev => [...prev.filter(t => t.id !== task.id), task])

  useEffect(() => subscribe((data) => {
    if (data.task?.workspace_id && data.task.workspace_id !== workspaceId) return
    if (data.type === 'task_suggested' || data.type === 'task_created' || data.type === 'task_updated') upsertTask(data.task)
    if (data.type === 'task_deleted' && (!data.workspace_id || data.workspace_id === workspaceId)) setTasks(prev => prev.filter(t => t.id !== data.task_id))
  }), [subscribe, workspaceId])

  const { needsDecision, overdue, dueSoon, highPriority } = groupTasks(tasks)

  // Re-throws after toasting (unlike dismiss/complete below) so FluidButton's own success/error
  // state - the checkmark morph - only ever fires on a real success, never on a swallowed failure.
  const accept = (task) => updateTaskStatus(token, task.id, 'pending').then(upsertTask).catch(err => { pushToast(err.detail || ACTION_FAILED); throw err })
  const dismiss = (task) => updateTaskStatus(token, task.id, 'dismissed').then(upsertTask).catch(err => pushToast(err.detail || ACTION_FAILED))
  const complete = (task) => updateTaskStatus(token, task.id, 'completed').then(upsertTask).catch(err => pushToast(err.detail || ACTION_FAILED))

  // Accept may come back reporting a schedule conflict instead of accepting - the modal below
  // lets the user pick an alternative/custom time, keep the original anyway, or dismiss instead.
  const { conflict, busy, accept, pickTime, acceptAnyway, close } = useTaskAccept({
    token, onUpdate: upsertTask, onError: err => pushToast(err.detail || ACTION_FAILED),
  })
  const dismissConflicted = (task) => { dismiss(task); close() }

  const totalInboxCount = needsDecision.length + overdue.length + dueSoon.length + highPriority.length

  const Section = ({ icon, title, items, tone, actions }) => {
    if (!items.length) return null
    return (
      <section className="suggested-section">
        <div className="section-heading">
          <div>
            <span className="ai-label"><i className={`bi ${icon}`} /> {title}</span>
            <h3>{items.length} {items.length === 1 ? 'item' : 'items'}</h3>
          </div>
        </div>
        <div className="suggestion-grid">
          {items.map(task => (
            <div className="suggestion-card" key={task.id}>
              <div className={`suggestion-check text-${tone}`}><i className="bi bi-flag-fill" /></div>
              <div className="flex-grow-1">
                <h4>{task.title}</h4>
                <div className="suggestion-meta">
                  <span><i className="bi bi-chat-left-text" />{sourceLabel[task.source] || task.source}</span>
                  <span><i className="bi bi-calendar3" />{formatDue(task.due_at)}</span>
                  <span><span className={`soft-badge ${priorityClass[task.priority]}`}><i />{task.priority}</span></span>
                </div>
              </div>
              <div className="suggestion-actions">{actions(task)}</div>
            </div>
          ))}
        </div>
      </section>
    )
  }

  return (
    <HologramSurface className="page-container orbit-fx">
      <PageHeader
        eyebrow="Personal"
        title="Task Inbox"
        description="What needs your attention first — ranked, not just listed."
        action={<Link to="/tasks" className="btn btn-light rounded-3"><i className="bi bi-list-task me-2" />All tasks</Link>}
      />
      <div className="stats-grid">
        <StatCard label="Needs decision" value={needsDecision.length} icon="bi-stars" color={needsDecision.length ? 'primary' : 'success'} />
        <StatCard label="Overdue" value={overdue.length} icon="bi-exclamation-circle" color={overdue.length ? 'danger' : 'success'} />
        <StatCard label="Due within 48h" value={dueSoon.length} icon="bi-hourglass-split" color={dueSoon.length ? 'warning' : 'success'} />
        <StatCard label="High priority" value={highPriority.length} icon="bi-flag" color={highPriority.length ? 'warning' : 'success'} />
      </div>

      {loading && <p className="text-muted small p-3 mb-0">Loading...</p>}

      {!loading && totalInboxCount === 0 && (
        <div className="content-card p-4 text-center text-muted">
          <i className="bi bi-check2-circle fs-3 d-block mb-2 text-success" />
          You're all caught up — nothing overdue, due soon, or waiting on a decision.
        </div>
      )}

      <Section
        icon="bi-stars" title="Needs your decision" items={needsDecision} tone="primary"
        actions={(task) => <>
          <FluidButton label="Accept" className="btn btn-sm btn-primary" onClick={() => accept(task)} />
          <button className="btn btn-sm btn-light" onClick={() => dismiss(task)}>Dismiss</button>
        </>}
      />
      <Section
        icon="bi-exclamation-circle" title="Overdue" items={overdue} tone="danger"
        actions={(task) => <button className="btn btn-sm btn-primary" onClick={() => complete(task)}>Complete</button>}
      />
      <Section
        icon="bi-hourglass-split" title="Due within 48 hours" items={dueSoon} tone="warning"
        actions={(task) => <button className="btn btn-sm btn-primary" onClick={() => complete(task)}>Complete</button>}
      />
      <Section
        icon="bi-flag" title="High priority" items={highPriority} tone="warning"
        actions={(task) => <button className="btn btn-sm btn-primary" onClick={() => complete(task)}>Complete</button>}
      />
    </HologramSurface>
  )
}
