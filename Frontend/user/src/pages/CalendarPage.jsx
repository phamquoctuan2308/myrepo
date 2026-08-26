import { useEffect, useRef, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import momentTimezonePlugin from '@fullcalendar/moment-timezone'
import PageHeader from '../components/common/PageHeader'
import NewEventModal from '../components/calendar/NewEventModal'
import ConnectCalendarCard from '../components/calendar/ConnectCalendarCard'
import { useAuth } from '../context/AuthContext'
import { deleteCalendarEvent, disconnectCalendar, getCalendarConnection, listCalendarEvents } from '../api/calendar'
import { getColor } from '../utils/avatar'
import { HANOI_TZ, formatDateTime } from '../utils/datetime'

export default function CalendarPage() {
  const { token } = useAuth()
  const { subscribe } = useOutletContext()
  const [connected, setConnected] = useState(null)
  const [events, setEvents] = useState([])
  const [checking, setChecking] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [newEventOpen, setNewEventOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const visibleRange = useRef(null)

  const refresh = (range = visibleRange.current) => {
    setLoading(true); setError('')
    listCalendarEvents(token, range || {}).then(list => {
      setConnected(true)
      setEvents(list.map(event => ({ ...event, color: getColor(event.id) })))
    }).catch(err => {
      if (err.status === 409) { setConnected(false); setEvents([]) }
      else setError(err.detail?.message || err.detail || 'Could not load Google Calendar events.')
    }).finally(() => setLoading(false))
  }

  useEffect(() => {
    setChecking(true)
    getCalendarConnection(token).then(result => setConnected(result.connected)).catch(() => {})
      .finally(() => setChecking(false))
  }, [token])

  const onDatesSet = ({ start, end }) => {
    const range = { time_min: start.toISOString(), time_max: end.toISOString() }
    visibleRange.current = range
    refresh(range)
  }
  const upsertEvent = event => setEvents(previous => [...previous.filter(item => item.id !== event.id), { ...event, color: getColor(event.id) }])
  const removeEvent = eventId => setEvents(previous => previous.filter(item => item.id !== eventId))

  useEffect(() => subscribe(data => {
    if (data.type === 'calendar_event_created' || data.type === 'calendar_event_updated') upsertEvent(data.event)
    if (data.type === 'calendar_event_deleted') removeEvent(data.event_id)
  }), [subscribe])

  const removeSelected = async () => {
    if (!selected || deleting) return
    setDeleting(true)
    try { await deleteCalendarEvent(token, selected.id); removeEvent(selected.id); setSelected(null) }
    catch (err) { setError(err.detail?.message || err.detail || 'Could not delete this event.') }
    finally { setDeleting(false) }
  }
  const disconnect = async () => {
    try { await disconnectCalendar(token); setConnected(false); setEvents([]) }
    catch (err) { setError(err.detail?.message || err.detail || 'Could not disconnect Google Calendar.') }
  }
  const action = connected ? <div className="d-flex gap-2"><button className="btn btn-light" onClick={disconnect}><i className="bi bi-google me-2" />Disconnect</button><button className="btn btn-primary" onClick={() => setNewEventOpen(true)}><i className="bi bi-plus-lg me-2" />New event</button></div> : null

  return <div className="page-container calendar-page">
    <PageHeader eyebrow="Schedule" title="Calendar" description="Your private Google Calendar, available to Orbit after you connect it." action={action} />
    {error && <div className="auth-error mb-3">{error}</div>}
    {checking ? <p className="text-muted small">Loading calendar...</p> : connected === false ? <ConnectCalendarCard onConnected={() => { setConnected(true); refresh() }} /> : <div className="calendar-layout"><section className="content-card calendar-card">
      {loading && <p className="text-muted small mb-2">Refreshing calendar...</p>}
      <FullCalendar plugins={[dayGridPlugin,timeGridPlugin,interactionPlugin,momentTimezonePlugin]} initialView="dayGridMonth" timeZone={HANOI_TZ} headerToolbar={{left:'prev,next today',center:'title',right:'dayGridMonth,timeGridWeek,timeGridDay'}} events={events} eventClick={({event,jsEvent})=>{jsEvent.preventDefault();setSelected(event)}} datesSet={onDatesSet} height="auto" />
    </section><aside className="detected-sidebar"><div className="detected-head"><span><i className="bi bi-stars" /></span><div><h3>AI-detected events</h3><p>Consent-aware</p></div></div><p className="text-muted small">Group candidates still require a conversation manager to confirm them. The resulting event is written only to that manager's connected calendar. Review suggestions from the relevant conversation or <Link to="/tasks">Tasks</Link>.</p></aside></div>}
    {selected && <div className="modal-backdrop-custom" onClick={()=>setSelected(null)}><div className="event-modal" onClick={event=>event.stopPropagation()}><button className="icon-btn modal-close" onClick={()=>setSelected(null)}><i className="bi bi-x-lg" /></button><div className="event-modal-icon"><i className="bi bi-calendar-event" /></div><span className="eyebrow">Event details</span><h3>{selected.title}</h3><div className="event-detail-row"><i className="bi bi-clock" /><span><strong>{formatDateTime(selected.start)}</strong>{selected.end && <small>{' → '}{formatDateTime(selected.end)}</small>}</span></div>{selected.url && <a className="btn btn-primary w-100 mt-3" href={selected.url} target="_blank" rel="noreferrer">Open in Google Calendar</a>}<button className="btn btn-light text-danger w-100 mt-2" onClick={removeSelected} disabled={deleting}><i className="bi bi-trash me-2" />{deleting ? 'Deleting...' : 'Delete event'}</button></div></div>}
    <NewEventModal open={newEventOpen} onClose={() => setNewEventOpen(false)} onCreated={upsertEvent} />
  </div>
}
