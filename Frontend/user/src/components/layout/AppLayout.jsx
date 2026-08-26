import { useCallback, useRef, useState } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopNavbar from './TopNavbar'
import ReminderToast from './ReminderToast'
import TaskSuggestedToast from './TaskSuggestedToast'
import BudgetAlertToast from './BudgetAlertToast'
import TransitionVeil from '../fx/TransitionVeil'
import { useAuth } from '../../context/AuthContext'
import { useChatSocket } from '../../api/useWebSocket'
import { getNotificationPermission, notifyReminderFired, notifyTaskSuggested } from '../../utils/browserNotifications'

export default function AppLayout() {
  const [open, setOpen] = useState(false)
  const { token, user } = useAuth()
  const navigate = useNavigate()
  const handlersRef = useRef(new Set())
  const [toastReminder, setToastReminder] = useState(null)
  const [toastTask, setToastTask] = useState(null)
  const [toastBudget, setToastBudget] = useState(null)
  // Data Flight target (pillar 2): the Sidebar's Tasks nav icon, shared with TaskSuggestedToast so
  // it knows where to fly to. AppLayout is already the common ancestor of both, so a single ref
  // passed down one level is enough - no Context needed.
  const tasksIconRef = useRef(null)
  const [flightPulse, setFlightPulse] = useState(false)
  const onFlightArrive = useCallback(() => {
    setFlightPulse(true)
    setTimeout(() => setFlightPulse(false), 450)
  }, [])

  const subscribe = useCallback((handler) => {
    handlersRef.current.add(handler)
    return () => handlersRef.current.delete(handler)
  }, [])

  const { sendJson, connected: socketConnected } = useChatSocket(token, (data) => {
    handlersRef.current.forEach(handler => handler(data))
    if (data.type === 'reminder_fired') {
      setToastReminder(data.reminder)
      if (
        user?.preferences?.desktop_notifications === true &&
        document.visibilityState !== 'visible' &&
        getNotificationPermission() === 'granted'
      ) notifyReminderFired(data.reminder, { onClick: () => navigate('/reminders') })
    }
    if (data.type === 'task_suggested') {
      setToastTask(data.task)
      if (
        user?.preferences?.ai_suggestion_alerts === true &&
        document.visibilityState !== 'visible' &&
        getNotificationPermission() === 'granted'
      ) notifyTaskSuggested(data.task, { onClick: () => navigate('/tasks') })
    }
    if (data.type === 'usage_budget_alert') setToastBudget(data)
  })

  return (
    <div className="app-shell orbit-fx">
      <TransitionVeil />
      <Sidebar open={open} onClose={() => setOpen(false)} tasksIconRef={tasksIconRef} flightPulse={flightPulse} />
      <div className="app-column"><TopNavbar onMenu={() => setOpen(true)} /><main className="app-main"><Outlet context={{ sendJson, socketConnected, subscribe }} /></main></div>
      {toastReminder && <ReminderToast reminder={toastReminder} onClose={() => setToastReminder(null)} />}
      {toastTask && <TaskSuggestedToast task={toastTask} onClose={() => setToastTask(null)} tasksIconRef={tasksIconRef} onFlightArrive={onFlightArrive} />}
      {toastBudget && <BudgetAlertToast alert={toastBudget} onClose={() => setToastBudget(null)} />}
    </div>
  )
}
