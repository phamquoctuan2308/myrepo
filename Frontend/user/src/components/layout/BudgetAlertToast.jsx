import { useEffect } from 'react'
import { Link } from 'react-router-dom'

const LEVEL_COPY = {
  warning: { icon: 'bi-exclamation-triangle', title: 'Approaching daily AI budget' },
  exceeded: { icon: 'bi-x-octagon', title: 'Daily AI budget exceeded' },
}

// Admin-only: the backend only ever pushes `usage_budget_alert` to admin user ids (see
// usage_service._maybe_alert_budget), so no extra role check is needed here to decide whether to
// render it - a non-admin socket simply never receives this event type.
//
// Shared between the user app (AppLayout.jsx, for an admin using their own personal account) and
// the separate admin app (AdminShell.jsx) - each renders this from its own BrowserRouter, so
// `dashboardHref` (a same-app route to link "View Admin dashboard" to) must be passed in rather
// than hardcoded; omit it to hide the link (the user app has nowhere in-app to send an admin to
// the separate admin console).
export default function BudgetAlertToast({ alert, onClose, dashboardHref }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 15000)
    return () => clearTimeout(timer)
  }, [alert, onClose])

  const copy = LEVEL_COPY[alert.level] || LEVEL_COPY.warning

  return (
    <div className="budget-alert-toast" role="alert" style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1090, maxWidth: 340 }}>
      <div className={`border rounded-3 p-3 bg-body shadow-lg d-flex align-items-start gap-2 border-${alert.level === 'exceeded' ? 'danger' : 'warning'}`}>
        <i className={`bi ${copy.icon} fs-5 text-${alert.level === 'exceeded' ? 'danger' : 'warning'}`} />
        <div className="flex-grow-1">
          <strong className="d-block">{copy.title}</strong>
          <small className="text-muted d-block">
            {alert.tokens_used_today.toLocaleString()} / {alert.daily_token_budget.toLocaleString()} tokens today ({alert.used_pct}%)
          </small>
          {dashboardHref && <Link to={dashboardHref} className="small" onClick={onClose}>View Admin dashboard</Link>}
        </div>
        <button className="btn-close" aria-label="Close" onClick={onClose} />
      </div>
    </div>
  )
}
