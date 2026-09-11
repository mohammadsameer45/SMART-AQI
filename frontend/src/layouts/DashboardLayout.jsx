import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { SelectionProvider } from '../components/SelectionContext'
import AreaPicker from '../components/AreaPicker'
import { useAlertsWatcher } from '../hooks/useAlertsWatcher'
import './dashboard.css'

const LINKS = [
  { to: '/app', label: 'Overview', end: true, icon: '◐' },
  { to: '/app/monitor', label: 'AQI Monitor', icon: '◉' },
  { to: '/app/forecast', label: 'Forecast', icon: '⇢' },
  { to: '/app/explorer', label: 'District Explorer', icon: '⊞' },
  { to: '/app/state', label: 'State Overview', icon: '◱' },
  { to: '/app/map', label: '3D AQI Map', icon: '◍' },
  { to: '/app/leaderboard', label: 'Leaderboard', icon: '⇕' },
  { to: '/app/pollutants', label: 'Pollutants', icon: '≋' },
  { to: '/app/health', label: 'Health Advisory', icon: '✚' },
  { to: '/app/models', label: 'Model Insights', icon: '⟐' },
  { to: '/app/settings', label: 'Settings', icon: '⚙' },
]

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  useAlertsWatcher()

  return (
    <SelectionProvider>
      <div className="dash">
        <aside className={`dash-side ${open ? 'open' : ''}`}>
          <Link to="/" className="brand" style={{ padding: '4px 8px 18px' }}>
            <span className="brand-mark" /> SMART <span className="brand-thin">AQI</span>
          </Link>
          <nav className="dash-nav">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} onClick={() => setOpen(false)}
                className={({ isActive }) => `dash-link ${isActive ? 'active' : ''}`}>
                <span className="dl-icon">{l.icon}</span>{l.label}
              </NavLink>
            ))}
          </nav>
          <div className="dash-side-foot tiny muted">
            HISTORICAL 2015–2020 · LIVE CPCB feed<br />FORECAST next 7 days ({new Date().getFullYear()})
          </div>
        </aside>

        <div className="dash-main">
          <header className="dash-top">
            <button className="dash-burger" onClick={() => setOpen((o) => !o)} aria-label="Menu">☰</button>
            <AreaPicker compact />
            <div className="dash-top-right">
              <div className="dash-user">
                <span className="dash-avatar">{(user?.name || 'U')[0].toUpperCase()}</span>
                <span className="dash-user-name">{user?.name}</span>
              </div>
              <button className="btn btn-ghost dash-logout" onClick={logout}>Log out</button>
            </div>
          </header>
          <div className="dash-content"><Outlet /></div>
        </div>
      </div>
    </SelectionProvider>
  )
}
