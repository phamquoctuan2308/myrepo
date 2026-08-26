import { useState } from 'react'
import PageHeader from '../components/common/PageHeader'
import SettingsSection from '../components/profile/SettingsSection'
import SupportGrantPanel from '../components/workspace/SupportGrantPanel'
import { useAuth } from '../context/AuthContext'
import { useWorkspace } from '../context/WorkspaceContext'
import { getNotificationPermission, isNotificationSupported, requestNotificationPermission } from '../utils/browserNotifications'

const DEFAULT_PREFS = { default_reminder_lead_minutes: 30, desktop_notifications: true, ai_suggestion_alerts: false, permission_scope: 'latest_20' }

export default function ProfilePage(){
  const { user, updateProfile, changePassword } = useAuth()
  const { workspace, workspaceId } = useWorkspace()
  const [form, setForm] = useState(() => ({ display_name: user?.display_name || '', job_title: user?.job_title || '', timezone: user?.timezone || 'Asia/Ho_Chi_Minh', ...DEFAULT_PREFS, ...(user?.preferences || {}) }))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [pw, setPw] = useState({ current_password: '', new_password: '' })
  const [pwStatus, setPwStatus] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const [notificationPermission, setNotificationPermission] = useState(() => getNotificationPermission())

  const set = key => e => setForm(f => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const setAiSuggestionAlerts = async event => {
    const enabled = event.target.checked
    if (enabled && isNotificationSupported() && getNotificationPermission() === 'default') {
      setNotificationPermission(await requestNotificationPermission())
    }
    setForm(current => ({ ...current, ai_suggestion_alerts: enabled }))
  }

  const setDesktopNotifications = async event => {
    const enabled = event.target.checked
    if (enabled && isNotificationSupported() && getNotificationPermission() === 'default') {
      setNotificationPermission(await requestNotificationPermission())
    }
    setForm(current => ({ ...current, desktop_notifications: enabled }))
  }

  const save = async () => {
    setSaving(true); setError('')
    try {
      const { display_name, job_title, timezone } = form
      const preferences = {
        default_reminder_lead_minutes: Number(form.default_reminder_lead_minutes),
        desktop_notifications: Boolean(form.desktop_notifications),
        ai_suggestion_alerts: Boolean(form.ai_suggestion_alerts),
        permission_scope: form.permission_scope,
      }
      await updateProfile({ display_name, job_title, timezone, preferences })
      setSaved(true); setTimeout(() => setSaved(false), 1800)
    } catch (err) { setError(err.detail || 'Could not save changes.') }
    finally { setSaving(false) }
  }

  const submitPassword = async () => {
    setPwSaving(true); setPwStatus('')
    try {
      await changePassword(pw)
      setPw({ current_password: '', new_password: '' })
      setPwStatus('Password updated.')
    } catch (err) { setPwStatus(err.detail || 'Could not change password.') }
    finally { setPwSaving(false) }
  }

  const initials = (user?.display_name || '?').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()
  const filled = [form.display_name, form.job_title, form.timezone, user?.email].filter(Boolean).length
  const completion = Math.round((filled / 4) * 100)
  const canApproveSupport = ['owner', 'admin'].includes(workspace?.current_user_role)

  return <div className="page-container profile-page"><PageHeader eyebrow="Account" title="Profile & settings" description="Manage your personal details and Orbit preferences." action={<button className="btn btn-primary" onClick={save} disabled={saving}><i className={`bi ${saved?'bi-check2':'bi-floppy'} me-2`}/>{saving?'Saving...':saved?'Saved':'Save changes'}</button>}/>
    {error && <div className="auth-error">{error}</div>}
    <div className="profile-layout"><aside className="profile-card"><div className="profile-avatar">{initials}</div><h2>{user?.display_name}</h2><p>{user?.email}</p><span>{form.job_title || 'No job title set'}</span><div className="profile-completion"><div><strong>Profile completion</strong><b>{completion}%</b></div><div className="progress"><div className="progress-bar" style={{width:`${completion}%`}}/></div></div><nav><a href="#basic" className="active"><i className="bi bi-person"/>Basic information</a><a href="#preferences"><i className="bi bi-sliders"/>Preferences</a><a href="#notifications"><i className="bi bi-bell"/>Notifications</a><a href="#ai"><i className="bi bi-stars"/>AI settings</a><a href="#security"><i className="bi bi-shield-lock"/>Security</a>{canApproveSupport && <a href="#support"><i className="bi bi-life-preserver"/>Support access</a>}</nav></aside><div className="settings-stack">
      <SettingsSection id="basic" icon="bi-person" title="Basic information" description="Your personal details and contact information."><div className="form-grid"><label><span>Full name</span><input className="form-control" autoComplete="name" value={form.display_name} onChange={set('display_name')}/></label><label><span>Email address</span><input className="form-control" autoComplete="email" value={user?.email || ''} disabled/></label><label><span>Job title</span><input className="form-control" autoComplete="organization-title" value={form.job_title} onChange={set('job_title')}/></label><label><span>Timezone</span><select className="form-select" value={form.timezone} onChange={set('timezone')}><option value="Asia/Ho_Chi_Minh">Bangkok/Hanoi (GMT+7)</option><option value="Europe/London">London (GMT+0)</option><option value="America/New_York">New York (GMT-5)</option></select></label></div></SettingsSection>
      <SettingsSection id="preferences" icon="bi-sliders" title="Preferences" description="Customize reminder defaults."><div className="form-grid"><label><span>Default reminder time</span><select className="form-select" value={form.default_reminder_lead_minutes} onChange={set('default_reminder_lead_minutes')}><option value="15">15 minutes before</option><option value="30">30 minutes before</option><option value="60">1 hour before</option></select></label></div></SettingsSection>
      <SettingsSection id="notifications" icon="bi-bell" title="Notifications" description="Choose when browser notifications are shown."><SettingToggle title="Desktop notifications" detail="Show reminders when Orbit is in the background" checked={form.desktop_notifications} onChange={setDesktopNotifications} warning={form.desktop_notifications && notificationPermission === 'denied' ? 'Browser notifications are blocked for this site.' : null}/><SettingToggle title="AI suggestion alerts" detail="Show detected task alerts when Orbit is in the background" checked={form.ai_suggestion_alerts} onChange={setAiSuggestionAlerts} warning={form.ai_suggestion_alerts && notificationPermission === 'denied' ? 'Browser notifications are blocked for this site.' : form.ai_suggestion_alerts && notificationPermission === 'unsupported' ? 'This browser only supports in-app alerts.' : null}/></SettingsSection>
      <SettingsSection id="ai" icon="bi-stars" title="AI settings" description="Choose the default conversation context scope."><div className="form-grid"><label><span>Default permission scope</span><select className="form-select" value={form.permission_scope} onChange={set('permission_scope')}><option value="latest_20">20 latest messages</option><option value="latest_50">50 latest messages</option><option value="unread">Unread messages</option></select></label></div></SettingsSection>
      <SettingsSection id="security" icon="bi-shield-lock" title="Security" description="Keep your account safe."><div className="security-row"><div><strong>Change password</strong><p>{pwStatus || 'Choose a new password for your account.'}</p></div></div><div className="form-grid"><label><span>Current password</span><input type="password" className="form-control" autoComplete="current-password" value={pw.current_password} onChange={e=>setPw(p=>({...p,current_password:e.target.value}))}/></label><label><span>New password</span><input type="password" className="form-control" autoComplete="new-password" value={pw.new_password} onChange={e=>setPw(p=>({...p,new_password:e.target.value}))}/></label></div><button className="btn btn-light mt-2" onClick={submitPassword} disabled={pwSaving || !pw.current_password || pw.new_password.length<6}>{pwSaving?'Updating...':'Update password'}</button></SettingsSection>
      {canApproveSupport && <div id="support"><SupportGrantPanel workspaceId={workspaceId} canApprove /></div>}
    </div></div></div>
}

function SettingToggle({title,detail,checked=false,onChange,warning}){return <div className="setting-toggle"><div><strong>{title}</strong><p>{detail}</p>{warning && <p className="text-warning small mb-0"><i className="bi bi-exclamation-triangle me-1"/>{warning}</p>}</div><div className="form-check form-switch"><input className="form-check-input" type="checkbox" checked={checked} onChange={onChange}/></div></div>}
