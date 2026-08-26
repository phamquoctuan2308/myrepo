import { apiFetch } from './client'

export const getStats = (token) => apiFetch('/admin/stats', { token })

export const getAIManagement = (token) => apiFetch('/admin/ai-management', { token })
export const updateAIManagement = (token, body) =>
  apiFetch('/admin/ai-management', { method: 'PATCH', token, body })
export const getSystemHealth = (token) => apiFetch('/admin/system-health', { token })
export const getAIUsage = (token, days = 7) => apiFetch(`/admin/ai-usage?days=${days}`, { token })
export const updateDailyBudget = (token, daily_token_budget) =>
  apiFetch('/admin/settings/budget', { method: 'PATCH', token, body: { daily_token_budget } })
export const listAuditLog = (
  token,
  { q = '', actorType = '', workspaceId = '', limit = 50, offset = 0 } = {},
) => {
  const params = new URLSearchParams({ limit, offset })
  if (q) params.set('q', q)
  if (actorType) params.set('actor_type', actorType)
  if (workspaceId) params.set('workspace_id', workspaceId)
  return apiFetch(`/admin/audit-log?${params}`, { token })
}

export const listUsers = (token, q = '') => {
  const params = new URLSearchParams({ limit: 500 })
  if (q) params.set('q', q)
  return apiFetch(`/admin/users?${params}`, { token })
}

export const listWorkspaces = (token, q = '') =>
  apiFetch(`/admin/workspaces?limit=500${q ? `&q=${encodeURIComponent(q)}` : ''}`, { token })

export const updateUserRole = (token, userId, role) =>
  apiFetch(`/admin/users/${userId}/role`, { method: 'PATCH', token, body: { role } })

export const updateUserStatus = (token, userId, is_active) =>
  apiFetch(`/admin/users/${userId}/status`, { method: 'PATCH', token, body: { is_active } })

const scopedParams = (workspaceId, ownerId) => {
  const params = new URLSearchParams({ workspace_id: workspaceId })
  if (ownerId) params.set('owner_id', ownerId)
  return params.toString()
}

export const listTasks = (token, workspaceId, ownerId) =>
  apiFetch(`/admin/tasks?${scopedParams(workspaceId, ownerId)}`, { token })

export const deleteTask = (token, workspaceId, taskId) =>
  apiFetch(`/admin/tasks/${taskId}?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'DELETE', token })

export const listReminders = (token, workspaceId, ownerId) =>
  apiFetch(`/admin/reminders?${scopedParams(workspaceId, ownerId)}`, { token })

export const deleteReminder = (token, workspaceId, reminderId) =>
  apiFetch(`/admin/reminders/${reminderId}?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'DELETE', token })

export const listMemories = (token, workspaceId, ownerId) =>
  apiFetch(`/admin/memories?${scopedParams(workspaceId, ownerId)}`, { token })

export const deleteMemory = (token, workspaceId, memoryId) =>
  apiFetch(`/admin/memories/${memoryId}?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'DELETE', token })
