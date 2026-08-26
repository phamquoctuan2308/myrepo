import { apiFetch } from './client'

export const listMemories = (token, workspaceId) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  return apiFetch(`/memories${params.toString() ? `?${params.toString()}` : ''}`, { token })
}

export const createMemory = (token, { workspace_id, category, title, detail }) =>
  apiFetch('/memories', { method: 'POST', token, body: { workspace_id, category, title, detail } })

export const updateMemory = (token, memoryId, updates) =>
  apiFetch(`/memories/${memoryId}`, { method: 'PATCH', token, body: updates })

export const deleteMemory = (token, memoryId) =>
  apiFetch(`/memories/${memoryId}`, { method: 'DELETE', token })
