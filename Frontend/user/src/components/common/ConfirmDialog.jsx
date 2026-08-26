export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Xoá',
  cancelLabel = 'Huỷ',
  danger = true,
  onConfirm,
  onCancel,
}) {
  if (!open) return null
  return (
    <div className="modal show d-block" tabIndex="-1" style={{ background: 'rgba(20,30,50,.32)' }} onClick={onCancel}>
      <div className="modal-dialog modal-dialog-centered" onClick={event => event.stopPropagation()}>
        <div className="modal-content">
          <div className="modal-header"><h5 className="modal-title">{title}</h5><button className="btn-close" onClick={onCancel} /></div>
          <div className="modal-body"><p className="mb-0">{message}</p></div>
          <div className="modal-footer">
            <button type="button" className="btn btn-light" onClick={onCancel}>{cancelLabel}</button>
            <button type="button" className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm}>{confirmLabel}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
