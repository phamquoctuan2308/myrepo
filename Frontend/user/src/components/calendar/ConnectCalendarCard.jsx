import { useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { getCalendarOAuthUrl } from '../../api/calendar'
import { API_BASE_URL } from '../../api/client'

const BACKEND_ORIGIN = new URL(API_BASE_URL).origin

export default function ConnectCalendarCard({ onConnected }) {
  const { token } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const connect = async () => {
    setBusy(true); setError('')
    try {
      const { url } = await getCalendarOAuthUrl(token)
      const popup = window.open(url, 'google-calendar-oauth', 'width=520,height=640')
      if (!popup) throw new Error('Popup blocked')
      const onMessage = event => {
        if (event.origin !== BACKEND_ORIGIN || event.data?.type !== 'calendar_oauth') return
        window.removeEventListener('message', onMessage)
        setBusy(false)
        if (event.data.ok) onConnected?.()
        else setError(event.data.message || 'Could not connect Google Calendar.')
      }
      window.addEventListener('message', onMessage)
      const timer = window.setInterval(() => {
        if (popup.closed) {
          window.clearInterval(timer)
          window.removeEventListener('message', onMessage)
          setBusy(false)
        }
      }, 500)
    } catch (err) {
      setError(err.detail?.message || err.detail || 'Could not open Google authorization.')
      setBusy(false)
    }
  }

  return <section className="content-card text-center py-5 px-3">
    <i className="bi bi-calendar-plus display-4 text-muted d-block mb-3" />
    <h3>Connect your Google Calendar</h3>
    <p className="text-muted mb-4">Events stay private to your account. Orbit stores the refresh token encrypted.</p>
    {error && <div className="auth-error mb-3">{error}</div>}
    <button className="btn btn-primary" onClick={connect} disabled={busy}><i className="bi bi-google me-2" />{busy ? 'Waiting for Google...' : 'Connect Google Calendar'}</button>
  </section>
}
