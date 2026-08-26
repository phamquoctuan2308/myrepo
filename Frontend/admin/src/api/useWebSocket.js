import { useEffect, useRef } from 'react'
import { apiFetch, WS_BASE_URL } from './client'

export function useAdminSocket(token, onMessage) {
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    if (!token) return undefined
    let cancelled = false
    let reconnectTimer
    let socket

    const connect = async () => {
      try {
        const { ticket } = await apiFetch('/auth/ws-ticket', { method: 'POST', token })
        if (cancelled) return
        socket = new WebSocket(`${WS_BASE_URL}?ticket=${encodeURIComponent(ticket)}`)
        socket.onmessage = event => {
          try { onMessageRef.current?.(JSON.parse(event.data)) } catch { /* malformed frame */ }
        }
        socket.onclose = () => { if (!cancelled) reconnectTimer = setTimeout(connect, 2000) }
      } catch {
        if (!cancelled) reconnectTimer = setTimeout(connect, 2000)
      }
    }
    connect()
    return () => {
      cancelled = true
      clearTimeout(reconnectTimer)
      if (socket?.readyState === WebSocket.CONNECTING) {
        socket.addEventListener('open', () => socket.close(), { once: true })
      } else if (socket?.readyState === WebSocket.OPEN) {
        socket.close()
      }
    }
  }, [token])
}
