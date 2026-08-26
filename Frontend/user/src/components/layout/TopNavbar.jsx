import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useWorkspace } from '../../context/WorkspaceContext'

const getInitials = (name) => (name || '?').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()

export default function TopNavbar({ onMenu }) {
  const { user, logout } = useAuth()
  const { workspaces, workspaceId, selectWorkspace } = useWorkspace()
  const navigate = useNavigate()
  const onLogout = () => { logout(); navigate('/login') }
  return (
    <header className="top-navbar">
      <button className="icon-btn mobile-menu" onClick={onMenu} aria-label="Open menu"><i className="bi bi-list" /></button>
      <div className="app-context"><i className="bi bi-command" /><strong>Orbit</strong></div>
      <div className="nav-actions">
        {workspaces.length > 1 && (
          <label className="workspace-switcher" aria-label="Active workspace">
            <i className="bi bi-buildings" />
            <select value={workspaceId || ''} onChange={event => selectWorkspace(event.target.value)}>
              {workspaces.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
            </select>
          </label>
        )}
        <button className="nav-avatar" onClick={() => navigate('/profile')} aria-label="Open profile" title="Profile">{getInitials(user?.display_name)}</button>
        <button className="icon-btn" onClick={onLogout} aria-label="Log out" title="Log out"><i className="bi bi-box-arrow-right" /></button>
      </div>
    </header>
  )
}
