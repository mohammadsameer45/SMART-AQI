import { useState } from 'react'
import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { aqi as aqiApi } from '../api/endpoints'
import SceneCanvas from '../three/SceneCanvas'
import ForecastRibbon from '../three/ForecastRibbon'
import { GlassCard, Loader, ErrorState, EmptyState, SectionTitle, AQIChip } from '../components/ui/Bits'
import { ForecastChart, Forecast24hChart } from '../charts/charts'
import { bandFor, aqiDisplay, fmtDateLong } from '../utils/aqi'
import { downloadForecastReport } from '../utils/report'
import './dash-pages.css'

const RANGES = [
  { key: '24h', label: '24 Hours' },
  { key: '3d', label: '3 Days' },
  { key: '7d', label: '7 Days' },
]

export default function ForecastPage() {
  const { state, area } = useSelection()
  const enabled = !!(state && area)
  const fc7 = useApi(() => aqiApi.forecast(state, area), [state, area], { enabled })
  const fc24 = useApi(() => aqiApi.forecast24h(state, area), [state, area], { enabled })
  const cur = useApi(() => aqiApi.current(state, area), [state, area], { enabled })
  const [range, setRange] = useState('7d')
  const [downloading, setDownloading] = useState(false)

  if (!state || !area) return <Loader />
  if (fc7.loading || fc24.loading) return <Loader label="Loading forecast…" />
  if (fc7.error) return <ErrorState error={fc7.error} onRetry={fc7.refetch} />

  const curBand = cur.data?.available ? bandFor(cur.data.AQI) : null
  const has7d = fc7.data?.forecast_available
  const has24h = fc24.data?.available

  const onDownload = async () => {
    setDownloading(true)
    try { downloadForecastReport({ state, area, current: cur.data, forecast: fc7.data }) }
    finally { setDownloading(false) }
  }

  if (!has7d && !has24h) {
    return (
      <div>
        <div className="page-head page-head-row">
          <div>
            <h1>AQI Forecast</h1>
            <p>Air-quality predictions for {area}, {state}.</p>
          </div>
        </div>
        <EmptyState title="No forecast for this area yet"
          hint={fc7.data?.reason || fc24.data?.reason} />
      </div>
    )
  }

  const daysToShow = range === '3d' ? (fc7.data?.days || []).slice(0, 3) : (fc7.data?.days || [])

  return (
    <div>
      <div className="page-head page-head-row">
        <div>
          <h1>AQI Forecast</h1>
          <p>Air-quality predictions for {area}, {state}.</p>
        </div>
        <button className="btn btn-ghost" onClick={onDownload} disabled={downloading || !has7d}>
          {downloading ? 'Preparing…' : '⭳ Download report'}
        </button>
      </div>

      <div className="fc-page-status">
        {cur.data?.available && (
          <div className="fc-status-chip">
            <span className="fc-status-label">
              <span className={`fc-live-dot ${cur.data.is_live ? 'on' : ''}`} />
              CURRENT AQI · {cur.data.is_live ? 'LIVE' : 'HISTORICAL'} · CPCB
            </span>
            <AQIChip label={`${aqiDisplay(cur.data.AQI)} · ${curBand?.label}`} color={curBand?.hex} />
          </div>
        )}
        <div className="range-toggle">
          {RANGES.map((r) => (
            <button key={r.key} className={range === r.key ? 'on' : ''} onClick={() => setRange(r.key)}>
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {range === '24h' ? <Forecast24hPanel fc24={fc24} /> : (
        has7d ? <ForecastDaysPanel data={fc7.data} days={daysToShow} /> : (
          <EmptyState title={`No ${range === '3d' ? '3-day' : '7-day'} model forecast for this area yet`}
            hint={fc7.data?.reason} />
        )
      )}

      <div className="grid g-2" style={{ marginTop: 18 }}>
        <OutdoorPlannerCard state={state} area={area} enabled={enabled} />
        <RecoveryCard state={state} area={area} enabled={enabled} />
      </div>
    </div>
  )
}

function ForecastDaysPanel({ data, days }) {
  return (
    <>
      <div className="banner">{data.note} {data.method ? `Method: ${data.method}.` : ''}
        {' '}Generated {fmtDateLong(data.generated_at)}. Horizon (+1d…) counts forward from this
        station's own last data point, which can lag today's calendar date — treat +1d… as the
        reliable label, not the printed date.</div>

      <GlassCard className="card" style={{ marginBottom: 18 }}>
        <SectionTitle eyebrow="Interactive 3D" title="Forecast ribbon" />
        <div className="canvas-box tall">
          <SceneCanvas camera={{ position: [0, 1.6, 8], fov: 46 }} style={{ width: '100%', height: '100%' }}
            fallback={<div />}>
            <ForecastRibbon days={days} />
          </SceneCanvas>
        </div>
        <div className="card-note">Drag to rotate · scroll to zoom · whiskers show the uncertainty band</div>
      </GlassCard>

      <div className="grid g-2">
        <GlassCard className="card">
          <SectionTitle eyebrow="2D" title="Predicted AQI with band" />
          <ForecastChart days={days} height={280} />
        </GlassCard>
        <GlassCard className="card">
          <SectionTitle title="Day by day" />
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Horizon</th><th>AQI</th><th>Category</th><th>Range</th></tr></thead>
              <tbody>
                {days.map((d) => {
                  const b = bandFor(d.predicted_AQI)
                  return (
                    <tr key={d.horizon_day}>
                      <td>
                        <b>+{d.horizon_day}d</b>
                        <div className="tiny muted">{fmtDateLong(d.forecast_date)}</div>
                      </td>
                      <td style={{ color: b?.hex, fontWeight: 700 }}>{Math.round(d.predicted_AQI)}</td>
                      <td><AQIChip label={b?.label} color={b?.hex} /></td>
                      <td className="muted tiny">{Math.round(d.lower)}–{Math.round(d.upper)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>
    </>
  )
}

function Forecast24hPanel({ fc24 }) {
  if (fc24.loading) return <Loader label="Loading 24-hour estimate…" />
  if (!fc24.data?.available) return <EmptyState title="No 24-hour estimate yet" hint={fc24.data?.reason} />
  const d = fc24.data
  return (
    <>
      <div className="banner">{d.note}</div>
      <div className="grid g-2">
        <GlassCard className="card">
          <SectionTitle eyebrow="2D" title="Next 24 hours" />
          <Forecast24hChart hours={d.hours} height={280} />
        </GlassCard>
        <GlassCard className="card">
          <SectionTitle title="Hour by hour" />
          <div className="table-scroll" style={{ maxHeight: 320, overflowY: 'auto' }}>
            <table className="table">
              <thead><tr><th>Time</th><th>AQI</th><th>Category</th></tr></thead>
              <tbody>
                {d.hours.map((h) => {
                  const b = bandFor(h.predicted_AQI)
                  return (
                    <tr key={h.time}>
                      <td>{h.hour_label}</td>
                      <td style={{ color: b?.hex, fontWeight: 700 }}>{Math.round(h.predicted_AQI)}</td>
                      <td><AQIChip label={b?.label} color={b?.hex} /></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>
    </>
  )
}

function OutdoorPlannerCard({ state, area, enabled }) {
  const p = useApi(() => aqiApi.outdoorPlanner(state, area), [state, area], { enabled })
  return (
    <GlassCard className="card">
      <SectionTitle eyebrow="Guidance" title="Outdoor walk planner" />
      {p.loading ? <Loader /> : !p.data?.available ? (
        <p className="tiny muted">{p.data?.reason || 'Unavailable.'}</p>
      ) : (
        <>
          <div className="kv" style={{ border: 'none' }}>
            <span>🟢 Best time</span>
            <span>{p.data.best_window.start}–{p.data.best_window.end} · AQI {p.data.best_window.min_AQI}–{p.data.best_window.max_AQI}</span>
          </div>
          <div className="kv" style={{ border: 'none' }}>
            <span>🔴 Avoid</span>
            <span>{p.data.avoid_window.start}–{p.data.avoid_window.end} · AQI {p.data.avoid_window.min_AQI}–{p.data.avoid_window.max_AQI}</span>
          </div>
          <p className="card-note">{p.data.note}</p>
        </>
      )}
    </GlassCard>
  )
}

function RecoveryCard({ state, area, enabled }) {
  const r = useApi(() => aqiApi.recovery(state, area), [state, area], { enabled })
  return (
    <GlassCard className="card">
      <SectionTitle eyebrow="Guidance" title="Pollution recovery" />
      {r.loading ? <Loader /> : !r.data?.available ? (
        <p className="tiny muted">{r.data?.reason || 'Unavailable.'}</p>
      ) : (
        <>
          <div className="kv"><span>Current</span><span>{r.data.current_AQI} · {r.data.current_bucket}</span></div>
          <div className="kv"><span>Peak (3d)</span><span>{r.data.peak_AQI_last_3d}</span></div>
          <div className="kv">
            <span>Trend</span>
            <span>{r.data.trend ? `${r.data.trend.classification} (${r.data.trend.percent_change}%)` : '—'}</span>
          </div>
          <div className="kv">
            <span>Estimated recovery</span>
            <span>
              {r.data.estimated_recovery
                ? `${fmtDateLong(r.data.estimated_recovery.forecast_date)} · AQI ${r.data.estimated_recovery.predicted_AQI}`
                : '—'}
            </span>
          </div>
          <p className="card-note">{r.data.note}</p>
        </>
      )}
    </GlassCard>
  )
}
