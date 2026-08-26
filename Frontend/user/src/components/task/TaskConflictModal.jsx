import { useState } from 'react'
import { formatDateTime } from '../../utils/datetime'

// alt.start/alt.end (from calendar_service.suggest_alternative_slots) are naive local-time
// strings with no UTC offset, meant to be read in the app's calendar_timezone - same as
// AIPanel.jsx's identical calendar_event interrupt already displays them (raw, no Date()
// re-parsing: new Date() on an offset-less string is interpreted in the *browser's* timezone,
// which would silently show the wrong time for any viewer not in that timezone).
function formatSlot(iso) {
  const [date, time] = iso.split('T')
  const [, month, day] = date.split('-')
  return `${day}/${month} ${(time || '').slice(0, 5)}`
}

// Shown when POST /tasks/{id}/accept reports a schedule conflict (task_routes.py::accept_task) -
// lets the user pick one of the suggested free alternatives, type a custom date/time, or keep the
// original time anyway. Whatever they pick becomes the task's own due_at once accepted, so the
// Calendar event + Reminder created right after are built from that same single value.
export default function TaskConflictModal({ conflict, onPickTime, onAcceptAnyway, onDismiss, onClose, busy }) {
  const [custom, setCustom] = useState('')
  if (!conflict) return null

  const submitCustom = (e) => {
    e.preventDefault()
    if (custom) onPickTime(`${custom}:00`)
  }

  return (
    <div className="modal show d-block" tabIndex="-1" style={{ background: 'rgba(20,30,50,.32)' }} onClick={onClose}>
      <div className="modal-dialog modal-dialog-centered" onClick={e => e.stopPropagation()}>
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title"><i className="bi bi-exclamation-triangle text-warning me-2" />Lịch bị trùng</h5>
            <button className="btn-close" onClick={onClose} disabled={busy} />
          </div>
          <div className="modal-body d-flex flex-column gap-3">
            <p className="mb-0 small text-muted">
              "{conflict.task.title}" trùng giờ với {conflict.conflicts.length} sự kiện đã có trên Calendar của bạn:
            </p>
            <ul className="list-unstyled mb-0 small">
              {conflict.conflicts.map(c => (
                <li key={c.id} className="d-flex align-items-center gap-2 py-1">
                  <i className="bi bi-calendar3 text-danger" />
                  <span><strong>{c.title}</strong> — {formatDateTime(c.start)}{c.end ? ` → ${formatDateTime(c.end)}` : ''}</span>
                </li>
              ))}
            </ul>

            {conflict.alternatives.length > 0 && <div>
              <label className="form-label small mb-1">Giờ trống gợi ý</label>
              <div className="d-flex gap-2 flex-wrap">
                {conflict.alternatives.map((alt, i) => (
                  <button
                    key={i} type="button" className="btn btn-sm btn-outline-primary" disabled={busy}
                    onClick={() => onPickTime(alt.start)}
                  >
                    {formatSlot(alt.start)} - {formatSlot(alt.end)}
                  </button>
                ))}
              </div>
            </div>}

            <form onSubmit={submitCustom} className="d-flex align-items-end gap-2">
              <div className="flex-grow-1">
                <label className="form-label small mb-1">Hoặc chọn ngày giờ khác</label>
                <input type="datetime-local" className="form-control" value={custom} onChange={e => setCustom(e.target.value)} disabled={busy} />
              </div>
              <button type="submit" className="btn btn-sm btn-outline-primary" disabled={busy || !custom}>Đổi giờ này</button>
            </form>
          </div>
          <div className="modal-footer flex-wrap">
            <button type="button" className="btn btn-light" onClick={() => onDismiss(conflict.task)} disabled={busy}>
              <i className="bi bi-x-circle me-2" />Huỷ nhiệm vụ này
            </button>
            <button type="button" className="btn btn-outline-secondary" onClick={onClose} disabled={busy}>Để sau</button>
            <button type="button" className="btn btn-primary" onClick={onAcceptAnyway} disabled={busy}>Vẫn giữ giờ cũ</button>
          </div>
        </div>
      </div>
    </div>
  )
}
