// Both standalone frontends use the same API, but each app may keep its own
// conventional VITE_API_URL/VITE_WS_URL environment file.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1'
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/api/v1/ws'

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : 'Request failed')
    this.status = status
    this.detail = detail
  }
}

export async function apiFetch(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => item.msg || 'Invalid value').join(', ')
      : payload?.detail || res.statusText
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return null
  return res.json()
}
