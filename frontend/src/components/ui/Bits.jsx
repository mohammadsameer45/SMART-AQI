import './bits.css'

export function GlassCard({ children, className = '', ...rest }) {
  return <div className={`glass card ${className}`} {...rest}>{children}</div>
}

export function StatTile({ label, value, sub, accent }) {
  return (
    <div className="stat-tile glass">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={accent ? { color: accent } : undefined}>{value}</div>
      {sub && <div className="stat-sub tiny muted">{sub}</div>}
    </div>
  )
}

export function Loader({ label = 'Loading…' }) {
  return (
    <div className="loader-inline">
      <span className="spin" /> <span className="muted tiny">{label}</span>
    </div>
  )
}

export function EmptyState({ title, hint }) {
  return (
    <div className="empty glass">
      <div className="empty-title">{title}</div>
      {hint && <p className="tiny muted">{hint}</p>}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="empty glass">
      <div className="empty-title">Couldn’t load this</div>
      <p className="tiny muted">{error?.message || 'Please try again.'}</p>
      {onRetry && <button className="btn btn-ghost" onClick={onRetry} style={{ marginTop: 12 }}>Retry</button>}
    </div>
  )
}

export function AQIChip({ label, color, onClick }) {
  const Tag = onClick ? 'button' : 'span'
  return (
    <Tag className={`aqi-chip${onClick ? ' aqi-chip-btn' : ''}`} style={{ '--c': color }} onClick={onClick}>
      <span className="dot" /> {label}
    </Tag>
  )
}

export function SectionTitle({ eyebrow, title, right }) {
  return (
    <div className="section-title">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
      </div>
      {right}
    </div>
  )
}
