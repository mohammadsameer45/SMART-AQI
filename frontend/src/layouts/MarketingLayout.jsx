import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import './marketing.css'

const NAV = [
  { to: '/#features', label: 'Features' },
  { to: '/#forecast', label: 'Forecast' },
  { to: '/#insights', label: 'Insights' },
  { to: '/#technology', label: 'Technology' },
  { to: '/#about', label: 'About' },
]

export default function MarketingLayout() {
  const { user } = useAuth()
  return (
    <div className="mkt">
      <header className="mkt-nav">
        <div className="container mkt-nav-inner">
          <Link to="/" className="brand">
            <span className="brand-mark" /> SMART <span className="brand-thin">AQI</span>
          </Link>
          <nav className="mkt-links">
            {NAV.map((n) => <a key={n.to} href={n.to}>{n.label}</a>)}
          </nav>
          <Link to={user ? '/app' : '/login'} className="btn btn-primary">
            {user ? 'Open Dashboard' : 'Explore SMART AQI'}
          </Link>
        </div>
      </header>
      <main><Outlet /></main>
      <footer className="mkt-footer">
        <div className="container mkt-footer-inner">
          <div>
            <div className="brand"><span className="brand-mark" /> SMART <span className="brand-thin">AQI</span></div>
            <p className="tiny muted" style={{ maxWidth: 320, marginTop: 10 }}>
              Air quality intelligence for India — monitoring, 7-day forecasting and
              precautionary health guidance. Informational use only.
            </p>
          </div>
          <div className="tiny muted">
            Data: CPCB (Kaggle 2015–2020), geoBoundaries. Not medical advice.
            <br />© {new Date().getFullYear()} SMART AQI.
          </div>
        </div>
      </footer>
    </div>
  )
}
