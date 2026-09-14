import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { fire as fireApi } from '../api/endpoints'
import { GlassCard, Loader, ErrorState, EmptyState, SectionTitle } from '../components/ui/Bits'
import './dash-pages.css'
import './fire-impact.css'

const LEVEL_COLOR = { Low: '#7bb93f', Moderate: '#f0c030', High: '#e24b4b', Unknown: '#71717a' }

export default function FireImpact() {
  const { state, area } = useSelection()
  const enabled = !!(state && area)
  const impact = useApi(() => fireApi.impact(state, area), [state, area], { enabled })
  const events = useApi(() => fireApi.events(state, area), [state, area], { enabled })

  if (!state || !area) return <Loader />
  if (impact.loading) return <Loader label="Checking for nearby fires…" />
  if (impact.error) return <ErrorState error={impact.error} onRetry={impact.refetch} />
  if (!impact.data?.available) return <EmptyState title="Fire data unavailable" hint={impact.data?.reason} />

  const d = impact.data

  return (
    <div>
      <div className="page-head">
        <h1>Fire &amp; Smoke</h1>
        <p>{area}, {state} · satellite active-fire detections (NASA FIRMS)</p>
      </div>

      {d.show_warning && (
        <div className="fire-warning-popup">
          <div className="fire-warning-title">🔥 FIRE DETECTED</div>
          <p>Potential smoke impact detected.</p>
          <div className="kv"><span>Distance</span><span>{d.distance_km} km</span></div>
          {d.wind && (
            <div className="kv"><span>Wind</span><span>{d.wind.speed_kmh} km/h → {d.wind.direction}</span></div>
          )}
          {d.potentially_affected.length > 0 && (
            <div className="kv" style={{ display: 'block' }}>
              <span>Potentially affected</span>
              <div className="pill-row" style={{ marginTop: 6 }}>
                {d.potentially_affected.map((a) => <span key={a.city} className="src-chip up">⚠️ {a.city}</span>)}
              </div>
            </div>
          )}
          <div className="kv"><span>Potential PM2.5 impact</span><span>{d.potential_impact_level}</span></div>
        </div>
      )}

      {!d.fire_detected ? (
        <EmptyState title="No active fire detected" hint={d.message} />
      ) : (
        <div className="grid g-2" style={{ marginBottom: 18 }}>
          <GlassCard className="card">
            <SectionTitle eyebrow={d.label} title="Impact map" />
            <FireRadar fire={d.nearest_fire} wind={d.wind} radiusKm={events.data?.radius_km || 200} />
            <p className="card-note">{d.note}</p>
          </GlassCard>

          <GlassCard className="card">
            <SectionTitle title="Nearest fire" />
            <div className="kv"><span>Distance</span><span>{d.distance_km} km</span></div>
            <div className="kv"><span>Detected</span><span>{d.nearest_fire.acquired_date} {String(d.nearest_fire.acquired_time_utc).padStart(4, '0').replace(/(\d{2})(\d{2})/, '$1:$2')} UTC</span></div>
            <div className="kv"><span>Satellite / instrument</span><span>{d.nearest_fire.satellite} / {d.nearest_fire.instrument}</span></div>
            <div className="kv"><span>Confidence</span><span>{d.nearest_fire.confidence}</span></div>
            <div className="kv"><span>Fire radiative power</span><span>{d.nearest_fire.frp_mw} MW</span></div>
            {d.wind && (
              <>
                <div className="kv"><span>Wind</span><span>{d.wind.speed_kmh} km/h → {d.wind.direction}</span></div>
                <div className="kv"><span>Alignment</span><span>{d.alignment}</span></div>
              </>
            )}
            <div className="kv">
              <span>Potential impact</span>
              <span style={{ color: LEVEL_COLOR[d.potential_impact_level], fontWeight: 700 }}>{d.potential_impact_level}</span>
            </div>
          </GlassCard>
        </div>
      )}

      <GlassCard className="card">
        <SectionTitle eyebrow="NASA FIRMS · VIIRS" title={`All detections within ${events.data?.radius_km ?? 200} km`} />
        {events.loading ? <Loader /> : !events.data?.available ? (
          <p className="tiny muted">{events.data?.reason}</p>
        ) : events.data.count === 0 ? (
          <p className="tiny muted">{events.data.message}</p>
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Distance</th><th>Detected</th><th>Confidence</th><th>FRP (MW)</th></tr></thead>
              <tbody>
                {events.data.fires.map((f, i) => (
                  <tr key={i}>
                    <td>{f.distance_km} km</td>
                    <td>{f.acquired_date} {String(f.acquired_time_utc).padStart(4, '0').replace(/(\d{2})(\d{2})/, '$1:$2')} UTC</td>
                    <td>{f.confidence}</td>
                    <td>{f.frp_mw}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  )
}

function FireRadar({ fire, wind, radiusKm }) {
  const size = 280, cx = size / 2, cy = size / 2, maxR = size / 2 - 28
  const bearingAreaToFire = (fire.bearing_from_fire_to_area_deg + 180) % 360
  const rPx = Math.min((fire.distance_km / radiusKm) * maxR, maxR)
  const toXY = (bearingDeg, r) => {
    const rad = (bearingDeg * Math.PI) / 180
    return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)]
  }
  const [fx, fy] = toXY(bearingAreaToFire, rPx)
  const rings = [0.25, 0.5, 0.75, 1].map((f) => f * maxR)

  let conePath = null
  if (wind?.blowing_toward_deg != null) {
    const [x1, y1] = toXY(wind.blowing_toward_deg - 45, maxR)
    const [x2, y2] = toXY(wind.blowing_toward_deg + 45, maxR)
    conePath = `M ${cx} ${cy} L ${x1} ${y1} A ${maxR} ${maxR} 0 0 1 ${x2} ${y2} Z`
  }

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxHeight: 320 }}>
      {conePath && <path d={conePath} fill="rgba(226,75,75,0.12)" stroke="rgba(226,75,75,0.3)" />}
      {rings.map((r) => <circle key={r} cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.08)" />)}
      <text x={cx} y={cy - maxR - 10} textAnchor="middle" fontSize="10" fill="#71717a">N</text>
      <text x={cx + maxR + 12} y={cy + 4} textAnchor="middle" fontSize="10" fill="#71717a">E</text>
      <text x={cx} y={cy + maxR + 16} textAnchor="middle" fontSize="10" fill="#71717a">S</text>
      <text x={cx - maxR - 12} y={cy + 4} textAnchor="middle" fontSize="10" fill="#71717a">W</text>

      {wind?.blowing_toward_deg != null && (
        <line x1={cx} y1={cy} x2={toXY(wind.blowing_toward_deg, maxR - 6)[0]} y2={toXY(wind.blowing_toward_deg, maxR - 6)[1]}
          stroke="#38bdf8" strokeWidth="2" markerEnd="url(#arrow)" />
      )}
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#38bdf8" />
        </marker>
      </defs>

      <circle cx={cx} cy={cy} r="6" fill="#a78bfa" />
      <circle cx={fx} cy={fy} r="6" fill="#e24b4b" />
      <text x={fx} y={fy - 12} textAnchor="middle" fontSize="10" fill="#e24b4b">🔥 {fire.distance_km}km</text>
      <text x={cx} y={cy + 20} textAnchor="middle" fontSize="10" fill="#a78bfa">Selected area</text>
    </svg>
  )
}
