import { apiFetch } from './client'

export const login = ({ email, password }) => apiFetch('/auth/admin/login', { method: 'POST', body: { email, password } })
export const getMe = (token) => apiFetch('/auth/me', { token })
