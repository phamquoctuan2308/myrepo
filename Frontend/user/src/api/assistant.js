import { apiFetch } from './client'

export const listAssistantThreads = (token, workspaceId) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  return apiFetch(`/assistant/threads${params.toString() ? `?${params.toString()}` : ''}`, { token })
}

export const getAssistantThreadMessages = (token, threadId, workspaceId) => {
  const params = new URLSearchParams()
  if (workspaceId) params.set('workspace_id', workspaceId)
  return apiFetch(`/assistant/threads/${threadId}/messages${params.toString() ? `?${params.toString()}` : ''}`, { token })
}
