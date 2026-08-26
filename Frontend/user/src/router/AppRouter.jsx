import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '../components/layout/AppLayout'
import ProtectedRoute from './ProtectedRoute'

const LoginPage = lazy(() => import('../pages/LoginPage'))
const RegisterPage = lazy(() => import('../pages/RegisterPage'))
const ChatPage = lazy(() => import('../pages/ChatPage'))
const TaskPage = lazy(() => import('../pages/TaskPage'))
const TaskInboxPage = lazy(() => import('../pages/TaskInboxPage'))
const CalendarPage = lazy(() => import('../pages/CalendarPage'))
const ReminderPage = lazy(() => import('../pages/ReminderPage'))
const MemoryPage = lazy(() => import('../pages/MemoryPage'))
const ProfilePage = lazy(() => import('../pages/ProfilePage'))
const PersonalAssistantPage = lazy(() => import('../pages/PersonalAssistantPage'))

function RouteFallback() {
  return (
    <div className="d-flex justify-content-center align-items-center min-vh-100" role="status">
      <div className="spinner-border text-primary" aria-label="Loading page" />
    </div>
  )
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<Navigate to="/assistant" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/assistant" element={<PersonalAssistantPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/tasks" element={<TaskPage />} />
              <Route path="/tasks/inbox" element={<TaskInboxPage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/reminders" element={<ReminderPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/assistant" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
