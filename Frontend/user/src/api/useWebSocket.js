import { useEffect, useRef, useState } from 'react'
import { apiFetch, WS_BASE_URL } from './client'

export function useChatSocket(token, onMessage) {
  const socketRef = useRef(null)
  const onMessageRef = useRef(onMessage)
  const [connected, setConnected] = useState(false)
  onMessageRef.current = onMessage

  useEffect(() => {
    if (!token) {
      setConnected(false)
      return undefined
    }
    let cancelled = false
    let connectTimer
    let reconnectTimer

    const connect = async () => {
      if (cancelled) return
      let ticket
      try {
        ticket = (await apiFetch('/auth/ws-ticket', { method: 'POST', token })).ticket
      } catch {
        if (!cancelled) reconnectTimer = setTimeout(connect, 2000)
        return
      }
      if (cancelled) return
      const ws = new WebSocket(`${WS_BASE_URL}?ticket=${encodeURIComponent(ticket)}`)
      socketRef.current = ws
      ws.onopen = () => { if (!cancelled && socketRef.current === ws) setConnected(true) }
      ws.onmessage = (event) => {
        try { onMessageRef.current?.(JSON.parse(event.data)) } catch { /* ignore malformed frame */ }
      }
      ws.onclose = () => {
        if (socketRef.current === ws) socketRef.current = null
        setConnected(false)
        if (!cancelled) reconnectTimer = setTimeout(connect, 2000)
      }
    }
    // React Strict Mode mounts, cleans up, then mounts effects again in development. Deferring
    // by one task lets that trial cleanup cancel the connection before a socket is constructed.
    connectTimer = setTimeout(connect, 0)

    return () => {
      cancelled = true
      setConnected(false)
      clearTimeout(connectTimer)
      clearTimeout(reconnectTimer)
      const ws = socketRef.current
      socketRef.current = null
      if (!ws) return
      if (ws.readyState === WebSocket.CONNECTING) {
        ws.addEventListener('open', () => ws.close(), { once: true })
      } else if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [token])

  const sendJson = (obj) => {
    const ws = socketRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return false
    try {
      ws.send(JSON.stringify(obj))
      return true
    } catch {
      return false
    }
  }

  return { sendJson, connected }
}
