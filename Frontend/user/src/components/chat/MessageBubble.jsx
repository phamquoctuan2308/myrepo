import Avatar from '../common/Avatar'
import { getInitials, getColor, formatTime } from '../../utils/avatar'

export default function MessageBubble({ message, own }) {
  if (own) return (
    <div className="message-row own"><div className="message-content"><div className="message-bubble">{message.content}</div><div className="message-time">{formatTime(message.created_at)} <i className="bi bi-check2-all" /></div></div></div>
  )
  return (
    <div className="message-row"><Avatar initials={getInitials(message.sender_name)} color={getColor(message.sender_id)} size={34} /><div className="message-content"><div className="message-sender">{message.sender_name}</div><div className="message-bubble">{message.content}</div><div className="message-time">{formatTime(message.created_at)}</div></div></div>
  )
}
