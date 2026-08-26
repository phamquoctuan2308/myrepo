import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import DataFlightCard from '../fx/DataFlightCard'

export default function TaskSuggestedToast({ task, onClose, tasksIconRef, onFlightArrive }) {
  const cardRef = useRef(null)
  const [flying, setFlying] = useState(false)

  useEffect(() => {
    const timer = setTimeout(onClose, 8000)
    return () => clearTimeout(timer)
  }, [task, onClose])

  // Pillar 2: "Data Flight" - let the toast register on-screen first, then detach a copy of it
  // that visibly travels to the Sidebar's Tasks icon. Delayed so the user actually sees the toast
  // arrive before it starts leaving.
  useEffect(() => {
    const timer = setTimeout(() => setFlying(true), 900)
    return () => clearTimeout(timer)
  }, [task])

  return (
    <div className="task-suggested-toast" role="alert" style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1080, maxWidth: 320 }}>
      <div ref={cardRef} className="border rounded-3 p-3 bg-body shadow-lg d-flex align-items-start gap-2">
        <i className="bi bi-stars text-primary fs-5" />
        <div className="flex-grow-1">
          <strong className="d-block">Orbit spotted a commitment</strong>
          <small className="text-muted d-block">{task.title}</small>
          <Link to="/tasks" className="small" onClick={onClose}>Review in Tasks</Link>
        </div>
        <button className="btn-close" aria-label="Close" onClick={onClose} />
      </div>
      {flying && tasksIconRef?.current && (
        <DataFlightCard sourceRef={cardRef} targetRef={tasksIconRef} title={task.title} onArrive={onFlightArrive} />
      )}
    </div>
  )
}
