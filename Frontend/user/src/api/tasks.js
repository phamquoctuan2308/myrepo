import { apiFetch } from './client'

export const listTasks = (token, workspaceId) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  return apiFetch(`/tasks${params.toString() ? `?${params.toString()}` : ''}`, { token })
}

export const createTask = (token, { workspace_id, title, due_at, priority, conversation_id, source, source_message_ids, consent_scope_hash }) =>
  apiFetch('/tasks', { method: 'POST', token, body: { workspace_id, title, due_at, priority, conversation_id, source, source_message_ids, consent_scope_hash } })

export const updateTaskStatus = (token, taskId, status) =>
  apiFetch(`/tasks/${taskId}/status`, { method: 'PATCH', token, body: { status } })

export const deleteTask = (token, taskId) =>
  apiFetch(`/tasks/${taskId}`, { method: 'DELETE', token })
