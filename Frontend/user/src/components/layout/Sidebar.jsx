import { NavLink } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const nav = [
  ['assistant', 'bi-stars', 'AI Assistant'], ['chat', 'bi-chat-dots', 'Chats'], ['tasks', 'bi-check2-square', 'Tasks'],
  ['tasks/inbox', 'bi-inbox', 'Inbox'],
  ['calendar', 'bi-calendar4-week', 'Calendar'], ['reminders', 'bi-bell', 'Reminders'],
  ['memory', 'bi-stars', 'Memory'], ['profile', 'bi-person', 'Profile'],
]

const getInitials = (name) => (name || '?').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()

export default function Sidebar({ open, onClose, tasksIconRef, flightPulse }) {
  const { user, isAdmin } = useAuth()
  const adminUrl = import.meta.env.VITE_ADMIN_APP_URL || 'http://localhost:5174'
  return (
    <>
      <div className={`sidebar-backdrop ${open ? 'show' : ''}`} onClick={onClose} />
      {/* Structural sizing/position/mobile-slide behavior stays on `.app-sidebar` (orbit-fx.css,
          scoped `.orbit-fx .app-sidebar` overrides of Frontend/shared/styles.css) - the classes
          below are purely the cosmetic "floating glass panel" surface, per the Tailwind sidebar
          spec: detached margins, rounded corners, translucent blur, soft shadow. */}
      <aside className={`app-sidebar ${open ? 'open' : ''} rounded-2xl border border-white/10 bg-orbit-panel/85 backdrop-blur-xl shadow-orbit-panel`}>
        <div className="brand"><span className="brand-mark"><i className="bi bi-command" /></span><span>Orbit</span></div>
        <nav className="sidebar-nav">
          <div className="nav-caption">Personal</div>
          {nav.map(([path, icon, label]) => (
            // `end` matters here: without it, `/tasks` would also read as "active" while on
            // `/tasks/inbox` (NavLink prefix-matches by default), highlighting both at once.
            <NavLink key={path} to={`/${path}`} end onClick={onClose} className={({ isActive }) => `side-link ${label === 'AI Assistant' ? 'assistant-link' : ''} ${isActive ? 'active' : ''} ${path === 'tasks' && flightPulse ? 'flight-pulse' : ''}`}>
              <i className={`bi ${icon}`} ref={path === 'tasks' ? tasksIconRef : undefined} /><span>{label}</span>{label === 'AI Assistant' && <span className="new-pill">New</span>}
            </NavLink>
          ))}
          {isAdmin && <><div className="nav-caption">Administration</div><a className="side-link" href={adminUrl}><i className="bi bi-box-arrow-up-right" /><span>Open Admin</span></a></>}
        </nav>
        <div className="sidebar-bottom">
          <NavLink to="/profile" className="user-mini"><span className="avatar-photo">{getInitials(user?.display_name)}</span><span><strong>{user?.display_name || 'Loading...'}</strong><small>{user?.email}</small></span><i className="bi bi-three-dots ms-auto" /></NavLink>
        </div>
      </aside>
    </>
  )
}
