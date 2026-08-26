import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useAuth } from '../../context/AuthContext'
import { chatWithAgent, resumeAgent } from '../../api/agent'
import { getAssistantThreadMessages } from '../../api/assistant'
import ScanningBorder from '../fx/ScanningBorder'
import PulseWave from '../fx/PulseWave'
import ScrambledMarkdown from '../fx/ScrambledMarkdown'
import FluidButton from '../fx/FluidButton'
import { springs } from '../fx/springs'

const prompts = [
  { icon:'bi-sun', label:'Lên kế hoạch hôm nay', prompt:'Tổng hợp lịch, task và deadline của tôi hôm nay' },
  { icon:'bi-calendar-check', label:'Lịch sắp tới', prompt:'Tuần này tôi có những cuộc họp quan trọng nào?' },
  { icon:'bi-exclamation-diamond', label:'Deadline gần nhất', prompt:'Deadline nào đang đến gần và cần ưu tiên?' },
  { icon:'bi-journal-bookmark', label:'Tìm trong memory', prompt:'Tóm tắt những gì bạn nhớ về cách tôi làm việc' },
]

function describeInterrupt(interrupt) {
  const d = interrupt.draft
  if (interrupt.type === 'memory_write') return `Bạn có muốn Orbit ghi nhớ "${d.title}" cho các phiên sau?`
  if (interrupt.type === 'memory_delete') return `Bạn có muốn Orbit quên memory "${d.title}"?`
  if (interrupt.type === 'calendar_event') {
    if (d.conflicts?.length) {
      const clash = d.conflicts.map(c => c.title).join(', ')
      return `Khung giờ ${d.start} - ${d.end} bị trùng với "${clash}". Bạn có muốn tạo "${d.summary}" vào giờ đó, hay chọn giờ thay thế bên dưới?`
    }
    return `Bạn có muốn tạo sự kiện "${d.summary}" từ ${d.start} đến ${d.end}?`
  }
  if (interrupt.type === 'reminder') return `Bạn có muốn đặt nhắc nhở "${d.title}" lúc ${d.due_at}?`
  return 'Bạn có muốn xác nhận hành động này?'
}

// `threadId` is controlled from PersonalAssistantPage (not local state here) so the "Gần đây"
// sidebar and this chat panel stay in sync: selecting a past session sets it from outside, and this
// component reports back (onThreadIdChange) whenever the server mints a new one on the first
// message of a fresh session.
export default function PersonalAIChat({ onContext, threadId, onThreadIdChange, onActivity, workspaceId }) {
  const { token, user } = useAuth()
  const [draft,setDraft]=useState('')
  const [messages,setMessages]=useState([])
  // Which thread's history is currently reflected in `messages` - lets the load effect below tell
  // "just sent/received a turn in this same thread" (already up to date, no need to re-fetch) apart
  // from "the user picked a different thread from the sidebar" (needs a real fetch).
  const [loadedThreadId,setLoadedThreadId]=useState(null)
  const [pending,setPending]=useState(null)
  // Requests may finish after the user has selected another thread. Track activity by thread so
  // one request cannot paint a spinner or append its response into a different session.
  const [sendingThreadKeys,setSendingThreadKeys]=useState([])
  const activeThreadRef=useRef(threadId)
  activeThreadRef.current=threadId
  const threadKey=(id)=>id || '__new_thread__'
  const sending=sendingThreadKeys.includes(threadKey(threadId))
  const markSending=(key,value)=>setSendingThreadKeys(prev => value
    ? (prev.includes(key) ? prev : [...prev,key])
    : prev.filter(item=>item!==key))

  const pushMessage = (msg) => setMessages(prev => [...prev, { id: Date.now() + Math.random(), ...msg }])

  useEffect(() => {
    if (!threadId) { setMessages([]); setPending(null); setLoadedThreadId(null); return }
    if (threadId === loadedThreadId) return
    let cancelled = false
    getAssistantThreadMessages(token, threadId, workspaceId).then(history => {
      if (cancelled) return
      setMessages(history.map((m,i) => ({ id: `${threadId}-${i}`, own: m.role === 'user', text: m.content })))
      setPending(null)
      setLoadedThreadId(threadId)
    }).catch(() => { if (!cancelled) pushMessage({ text: 'Không tải được lịch sử cuộc trò chuyện.' }) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadedThreadId is the "already handled" guard, re-running on it would defeat that
  }, [threadId, token, workspaceId])

  const handleResult = (res, expectedThreadId=threadId) => {
    if (res.thread_id && res.thread_id !== expectedThreadId) onThreadIdChange?.(res.thread_id)
    setLoadedThreadId(res.thread_id)
    if (res.status === 'interrupted') {
      setPending({ thread_id: res.thread_id, interrupt: res.interrupt })
      // `fresh` (pillar 3, scramble-text): only ever set on a message just pushed from a live
      // response, never on history loaded from getAssistantThreadMessages - revisiting a past
      // thread must not re-scramble it.
      pushMessage({ text: describeInterrupt(res.interrupt), interrupt: res.interrupt, fresh: true })
    } else {
      pushMessage({ text: res.response || (res.status === 'error' ? 'Đã có lỗi xảy ra, thử lại sau.' : 'Orbit không có câu trả lời cho yêu cầu này.'), fresh: true })
    }
    if (res.status !== 'error') onActivity?.()
  }

  const send = async (value=draft) => {
    if(!value.trim() || sending) return
    const requestThreadId=threadId
    const requestKey=threadKey(requestThreadId)
    pushMessage({ own:true, text:value })
    setDraft('')
    markSending(requestKey,true)
    try {
      const res = await chatWithAgent(token, { message: value, thread_id: requestThreadId, workspace_id: workspaceId })
      if (activeThreadRef.current===requestThreadId) handleResult(res,requestThreadId)
      else onActivity?.() // result is persisted in its own checkpoint; refresh the sidebar only
    } catch (err) {
      if (activeThreadRef.current===requestThreadId) {
        pushMessage({ text: err.detail || 'Không gọi được AI Assistant, thử lại sau.' })
      }
    } finally { markSending(requestKey,false) }
  }

  const respond = async (approved, edits) => {
    if (!pending || sending) return
    const requestThreadId=threadId
    const requestKey=threadKey(requestThreadId)
    const requestPending=pending
    markSending(requestKey,true)
    try {
      const res = await resumeAgent(token, { thread_id: requestPending.thread_id, approved, edits })
      if (activeThreadRef.current===requestThreadId) {
        setPending(null)
        handleResult(res,requestThreadId)
      } else onActivity?.()
    } catch (err) {
      if (activeThreadRef.current===requestThreadId) {
        pushMessage({ text: err.detail || 'Không gọi được AI Assistant, thử lại sau.' })
      }
      // Re-thrown so FluidButton's own success/error state - the checkmark morph - only ever
      // fires on a real success, never on a swallowed failure.
      throw err
    } finally { markSending(requestKey,false) }
  }

  return <section className="personal-chat orbit-fx">
    <ScanningBorder active={sending} />
    <header className="personal-chat-header"><div className="personal-ai-avatar"><i className="bi bi-stars"/><span/></div><div><h3>Orbit Personal AI</h3><span><i/> Sẵn sàng hỗ trợ bạn</span></div><div className="personal-header-actions"><button className="context-mobile-btn" onClick={onContext}><i className="bi bi-layout-sidebar-reverse"/> Bối cảnh</button><button className="icon-btn" aria-label="Cuộc trò chuyện mới" onClick={()=>onThreadIdChange?.(null)}><i className="bi bi-arrow-clockwise"/></button></div></header>
    <div className="personal-messages bg-[radial-gradient(circle,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[length:22px_22px]">
      {messages.length===0 && <div className="personal-welcome"><motion.div initial={{scale:.85,opacity:0}} animate={{scale:1,opacity:1}} className="welcome-ai-mark"><i className="bi bi-stars"/></motion.div><span className="welcome-kicker">Chào {user?.display_name || 'bạn'}</span><h1>Hôm nay mình có thể<br/><em>giúp gì cho bạn?</em></h1><p>Hỏi mình về lịch, công việc, deadline hoặc thông tin từ các cuộc trò chuyện đã được cấp quyền.</p><div className="prompt-grid">{prompts.map(p=>
        // Glassmorphism prompt card: translucent fill + backdrop blur + a soft corner flare span
        // (Tailwind utilities can't target pseudo-elements, hence a plain absolutely-positioned
        // span) - `.prompt-grid button`'s grid layout itself stays in orbit-fx.css untouched.
        <motion.button
          whileHover={{y:-3}} whileTap={{scale:.98}} key={p.label} onClick={()=>send(p.prompt)}
          className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md transition-shadow duration-300 hover:shadow-orbit-glow"
        >
          <span aria-hidden className="pointer-events-none absolute -right-5 -top-5 h-16 w-16 rounded-full bg-orbit-glow-a/25 blur-2xl" />
          <span><i className={`bi ${p.icon}`}/></span><strong>{p.label}</strong><small>{p.prompt}</small><i className="bi bi-arrow-up-right"/>
        </motion.button>
      )}</div></div>}
      <AnimatePresence initial={false}>{messages.map(m=><motion.div key={m.id} layout initial={{opacity:0,y:18,scale:.97}} animate={{opacity:1,y:0,scale:1}} transition={springs.messageEnter} className={`personal-message ${m.own?'own':''}`}>
        {!m.own&&<div className="message-ai-icon"><i className="bi bi-stars"/></div>}<div><div className="personal-message-bubble">{m.own ? m.text : <ScrambledMarkdown text={m.text} active={Boolean(m.fresh)}/>}{m.interrupt && pending?.thread_id===threadId && <div className="d-flex gap-2 mt-2 flex-wrap">{m.interrupt.draft?.alternatives?.map((alt,i)=><button key={i} className="btn btn-sm btn-outline-primary" disabled={sending} onClick={()=>respond(true,{start:alt.start,end:alt.end}).catch(()=>{})}>Dùng {alt.start} - {alt.end}</button>)}<FluidButton label="Xác nhận" disabled={sending} onClick={()=>respond(true)}/><button className="btn btn-sm btn-light" disabled={sending} onClick={()=>respond(false).catch(()=>{})}>Huỷ</button></div>}</div><time>Bây giờ</time></div>
      </motion.div>)}</AnimatePresence>
      {sending && <div className="personal-message"><div className="message-ai-icon"><i className="bi bi-stars"/></div><div className="personal-message-bubble">Đang xử lý...</div></div>}
    </div>
    <PulseWave active={sending} />
    <div className="personal-composer-wrap"><div className="active-sources"><span><i className="bi bi-database-check"/> Nguồn khả dụng: Chats · Tasks · Calendar · Memory</span></div>{/* Floating glass composer: translucent blur + resting glow + a stronger glow ring on focus
          (Tailwind focus-within: variant) - `.personal-composer`'s own box model/flex layout and
          the existing orbit-fx.css glow stay as-is, these classes only add the glass surface. */}
      <form
        className="personal-composer backdrop-blur-md shadow-orbit-glow transition-shadow duration-300 focus-within:shadow-orbit-glow-focus focus-within:border-orbit-glow-a"
        onSubmit={e=>{e.preventDefault();send()}}
      >
        <textarea rows="1" value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Hỏi Orbit về công việc và lịch trình của bạn..." onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}/>
        <button className="personal-send" aria-label="Gửi" disabled={sending} onClick={e=>{e.preventDefault();send()}}><i className="bi bi-arrow-up"/></button>
      </form><small>Orbit có thể mắc lỗi. Hãy kiểm tra lại thông tin quan trọng.</small></div>
  </section>
}
