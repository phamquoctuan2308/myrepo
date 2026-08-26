import { apiFetch } from './client'

export const listReminders = (token, workspaceId) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  return apiFetch(`/reminders${params.toString() ? `?${params.toString()}` : ''}`, { token })
}

export const createReminder = (token, { workspace_id, title, due_at_iso, lead_minutes, message }) =>
  apiFetch('/reminders', { method: 'POST', token, body: { workspace_id, title, due_at_iso, lead_minutes, message } })

export const cancelReminder = (token, reminderId, workspaceId) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  return apiFetch(`/reminders/${reminderId}${params.toString() ? `?${params.toString()}` : ''}`, { method: 'DELETE', token })
}
