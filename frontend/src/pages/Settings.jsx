import { useAuth } from '../auth/AuthContext'
import { GlassCard, SectionTitle } from '../components/ui/Bits'
import './dash-pages.css'

export default function Settings() {
  const { user, logout } = useAuth()
  return (
    <div>
      <div className="page-head"><h1>Settings</h1><p>Account and data information.</p></div>

      <div className="grid g-2">
        <GlassCard className="card">
          <SectionTitle title="Profile" />
          <div className="kv"><span>Name</span><span>{user?.name}</span></div>
          <div className="kv"><span>Email</span><span>{user?.email}</span></div>
          <div className="kv"><span>Member since</span><span>{user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</span></div>
          <button className="btn btn-ghost" style={{ marginTop: 16 }} onClick={logout}>Log out</button>
        </GlassCard>

        <GlassCard className="card">
          <SectionTitle title="About the data" />
          <p className="tiny muted">
            HISTORICAL air-quality data from CPCB monitoring stations (Kaggle
            2015–2020 release), cleaned and validated. LIVE current readings and
            weather come from the CPCB real-time feed (data.gov.in) and
            Open-Meteo. District boundaries from geoBoundaries.
          </p>
          <p className="tiny muted" style={{ marginTop: 12 }}>
            Forecasts are model predictions, not measurements. Health guidance is
            informational and precautionary — not medical advice.
          </p>
        </GlassCard>
      </div>
    </div>
  )
}
