import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { useApi } from '../hooks/useApi'
import { useToast } from '../hooks/useToast'
import { geo, alerts as alertsApi } from '../api/endpoints'
import { GlassCard, SectionTitle, AQIChip, Loader } from '../components/ui/Bits'
import { bandFor, aqiDisplay } from '../utils/aqi'
import { pushSupported, enablePush, currentPushState } from '../utils/push'
import './dash-pages.css'
import './leaderboard.css'

function useAreasFor(state) {
  const [areas, setAreas] = useState([])
  useEffect(() => {
    if (!state) { setAreas([]); return }
    let alive = true
    geo.areas(state).then((r) => { if (alive) setAreas(r.items) }).catch(() => alive && setAreas([]))
    return () => { alive = false }
  }, [state])
  return areas
}

function AlertsCard() {
  const toast = useToast()
  const { data: states } = useApi(() => geo.states(), [])
  const { data: rules, loading, error, refetch } = useApi(() => alertsApi.list(), [])
  const [state, setState] = useState('')
  const [area, setArea] = useState('')
  const [threshold, setThreshold] = useState(150)
  const [saving, setSaving] = useState(false)
  const [pushState, setPushState] = useState('checking')
  const [enabling, setEnabling] = useState(false)
  const areas = useAreasFor(state)

  useEffect(() => { if (states?.length && !state) setState(states[0]) }, [states, state])
  useEffect(() => { currentPushState().then(setPushState) }, [])

  const addRule = async (e) => {
    e.preventDefault()
    if (!state || !area) { toast.error('Pick a state and area first.'); return }
    setSaving(true)
    try {
      await alertsApi.create(state, area, Number(threshold))
      toast.success(`Alert set for ${area}, ${state}.`)
      refetch()
    } catch (err) {
      toast.error(err.message || 'Could not create alert.')
    } finally {
      setSaving(false)
    }
  }

  const removeRule = async (id) => {
    try { await alertsApi.remove(id); refetch() }
    catch (err) { toast.error(err.message || 'Could not remove alert.') }
  }

  const enableNotifications = async () => {
    setEnabling(true)
    try {
      const on = await enablePush()
      setPushState(on ? 'subscribed' : await currentPushState())
      if (on) toast.success('Push notifications enabled — alerts will reach you even in the background.')
      else toast.error('Notifications were not enabled (permission denied or unsupported).')
    } catch (err) {
      toast.error(err.message || 'Could not enable push notifications.')
    } finally {
      setEnabling(false)
    }
  }

  return (
    <GlassCard className="card" style={{ marginTop: 18 }}>
      <SectionTitle eyebrow="Real-time" title="Air quality alerts" />
      <p className="tiny muted" style={{ marginBottom: 14 }}>
        Get notified when an area's current AQI reaches a threshold you set. Checked
        against the same live/historical current-AQI data as the rest of the app.
      </p>

      {pushState === 'subscribed' ? (
        <p className="tiny" style={{ color: 'var(--aqi-good)', marginBottom: 14 }}>
          ✓ Push notifications enabled on this browser.
        </p>
      ) : pushSupported() && pushState !== 'denied' ? (
        <button className="btn btn-ghost" style={{ marginBottom: 14 }} onClick={enableNotifications} disabled={enabling}>
          {enabling ? 'Enabling…' : '🔔 Enable push notifications'}
        </button>
      ) : pushState === 'denied' ? (
        <p className="tiny muted" style={{ marginBottom: 14 }}>
          Notifications are blocked for this site in your browser settings.
        </p>
      ) : (
        <p className="tiny muted" style={{ marginBottom: 14 }}>
          Push notifications aren't supported in this browser — you'll still see
          in-app alerts while SMART AQI is open.
        </p>
      )}

      {loading ? <Loader label="Loading alerts…" />
        : error ? <p className="tiny muted">{error.message}</p>
        : (
          <>
            {rules.length > 0 && (
              <div className="kv-list" style={{ marginBottom: 16 }}>
                {rules.map((r) => {
                  const band = r.current_aqi != null ? bandFor(r.current_aqi) : null
                  return (
                    <div key={r.id} className="alert-row">
                      <div>
                        <b>{r.area}</b><span className="tiny muted"> · {r.state}</span>
                        <div className="tiny muted">Alert above AQI {r.threshold}</div>
                      </div>
                      <div className="alert-row-right">
                        {r.current_aqi != null
                          ? <AQIChip label={`${aqiDisplay(r.current_aqi)} · ${r.is_live ? 'LIVE' : 'HISTORICAL'}`} color={band?.hex} />
                          : <span className="tiny muted">no reading</span>}
                        {r.triggered && <span className="alert-badge">TRIGGERED</span>}
                        <button className="btn btn-ghost cmp-remove" onClick={() => removeRule(r.id)} aria-label="Remove">✕</button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            <form className="cmp-row" onSubmit={addRule}>
              <select value={state} onChange={(e) => { setState(e.target.value); setArea('') }}>
                {(states || []).map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select value={area} onChange={(e) => setArea(e.target.value)}>
                <option value="">Select area…</option>
                {areas.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
              <input type="number" min="1" max="500" value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="alert-threshold-input" aria-label="AQI threshold" />
              <button className="btn btn-primary" type="submit" disabled={saving}>
                {saving ? 'Adding…' : '+ Add alert'}
              </button>
            </form>
          </>
        )}
    </GlassCard>
  )
}

export default function Settings() {
  const { user, logout } = useAuth()
  return (
    <div>
      <div className="page-head"><h1>Settings</h1><p>Account, alerts and data information.</p></div>

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

      <AlertsCard />
    </div>
  )
}
