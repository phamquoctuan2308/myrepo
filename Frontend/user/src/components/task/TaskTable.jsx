import { formatDateShort } from '../../utils/datetime'
import EmptyState from '../fx/EmptyState'

const priorityClass = { High: 'danger', Medium: 'warning', Low: 'info' }
const statusClass = { Completed: 'success', Overdue: 'danger', Pending: 'secondary', 'In progress': 'primary' }
const sourceLabel = { manual: 'Manual', proactive: 'AI suggestion' }

function displayStatus(task) {
  if (task.status === 'pending' && task.due_at && new Date(task.due_at) < new Date()) return 'Overdue'
  if (task.status === 'in_progress') return 'In progress'
  if (task.status === 'completed') return 'Completed'
  return 'Pending'
}

export function formatDue(due_at) {
  if (!due_at) return 'No due date'
  return formatDateShort(due_at)
}

export default function TaskTable({ tasks, onComplete, onDelete }) {
  return (
    <div className="table-responsive task-table-wrap"><table className="table task-table align-middle mb-0"><thead><tr><th><input type="checkbox"/></th><th>Task</th><th>Deadline</th><th>Priority</th><th>Status</th><th>Source</th><th/></tr></thead><tbody>
      {tasks.map(task => {
        const status = displayStatus(task)
        return <tr key={task.id}><td><input type="checkbox" checked={task.status==='completed'} readOnly/></td><td><strong className={task.status==='completed'?'text-decoration-line-through text-muted':''}>{task.title}</strong></td><td><span className={status==='Overdue'?'text-danger':''}><i className="bi bi-calendar3 me-2"/>{formatDue(task.due_at)}</span></td><td><span className={`soft-badge ${priorityClass[task.priority]}`}><i/>{task.priority}</span></td><td><span className={`status-badge ${statusClass[status]}`}>{status}</span></td><td><span className="source-pill"><i className="bi bi-chat-left-text"/>{sourceLabel[task.source] || task.source}</span></td><td><div className="dropdown"><button className="icon-btn" data-bs-toggle="dropdown"><i className="bi bi-three-dots"/></button><ul className="dropdown-menu dropdown-menu-end"><li><button className="dropdown-item" onClick={() => onComplete(task)}><i className="bi bi-check2 me-2"/>Complete</button></li><li><button className="dropdown-item text-danger" onClick={() => onDelete(task)}><i className="bi bi-trash me-2"/>Delete</button></li></ul></div></td></tr>
      })}
      {!tasks.length && <tr><td colSpan={7} className="p-0"><EmptyState variant="radar" icon="bi-check2-square" title="No tasks yet" description="Add one, or Orbit will surface tasks it finds in your conversations." /></td></tr>}
    </tbody></table></div>
  )
}
