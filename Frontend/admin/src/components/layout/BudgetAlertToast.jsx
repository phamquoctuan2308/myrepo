import { useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function BudgetAlertToast({ alert, onClose }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 15000)
    return () => clearTimeout(timer)
  }, [alert, onClose])

  const exceeded = alert.level === 'exceeded'
  return <div className="budget-alert-toast" role="alert" style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1090, maxWidth: 360 }}>
    <div className={`border rounded-3 p-3 bg-body shadow-lg d-flex align-items-start gap-2 border-${exceeded ? 'danger' : 'warning'}`}>
      <i className={`bi ${exceeded ? 'bi-x-octagon text-danger' : 'bi-exclamation-triangle text-warning'} fs-5`} />
      <div className="flex-grow-1"><strong className="d-block">{exceeded ? 'Daily AI budget exceeded' : 'Approaching daily AI budget'}</strong><small className="text-muted d-block">{alert.tokens_used_today.toLocaleString()} / {alert.daily_token_budget.toLocaleString()} tokens ({alert.used_pct}%)</small><Link to="/admin/ai" onClick={onClose}>Review AI budget</Link></div>
      <button className="btn-close" aria-label="Close" onClick={onClose} />
    </div>
  </div>
}
