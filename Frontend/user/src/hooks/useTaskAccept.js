import { useState } from 'react'
import { acceptTask } from '../api/tasks'

// Shared Accept flow for TaskPage.jsx and TaskInboxPage.jsx: accepting a proactively-suggested
// task with a due date can come back with a schedule conflict instead of accepting
// (POST /tasks/{id}/accept - see task_routes.py::accept_task). This hook holds that pending
// conflict so both pages can render TaskConflictModal and resolve it (pick an alternative slot, a
// custom date/time, or accept at the original time anyway) without duplicating the same state
// machine twice. Dismissing the task instead is the page's own existing dismiss() - not this hook.
export function useTaskAccept({ token, onUpdate, onError }) {
  // { task, dueAt, conflicts, alternatives } | null - dueAt is whatever time was just checked
  // (the task's own due_at on the first call, or the due_at a later call tried), so "accept
  // anyway" and a follow-up pick both act on the right time even across several conflicts in a row.
  const [conflict, setConflict] = useState(null)
  const [busy, setBusy] = useState(false)

  const accept = async (task, { due_at, force } = {}) => {
    setBusy(true)
    try {
      const res = await acceptTask(token, task.id, { due_at, force })
      onUpdate(res.task)
      setConflict(res.conflict ? { task, dueAt: due_at || task.due_at, conflicts: res.conflicts, alternatives: res.alternatives } : null)
    } catch (err) {
      onError(err)
    } finally {
      setBusy(false)
    }
  }

  return {
    conflict,
    busy,
    accept,
    pickTime: (dueAt) => accept(conflict.task, { due_at: dueAt }),
    acceptAnyway: () => accept(conflict.task, { due_at: conflict.dueAt, force: true }),
    close: () => setConflict(null),
  }
}
