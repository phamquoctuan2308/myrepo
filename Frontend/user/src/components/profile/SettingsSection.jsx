export default function SettingsSection({ id, icon, title, description, children }) {
  return <section id={id} className="settings-section"><div className="settings-section-head"><span><i className={`bi ${icon}`}/></span><div><h3>{title}</h3><p>{description}</p></div></div><div className="settings-section-body">{children}</div></section>
}
