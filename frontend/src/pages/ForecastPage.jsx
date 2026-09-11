import { useState } from 'react'
import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { aqi as aqiApi } from '../api/endpoints'
import SceneCanvas from '../three/SceneCanvas'
import ForecastRibbon from '../three/ForecastRibbon'
import { GlassCard, Loader, ErrorState, EmptyState, SectionTitle, AQIChip } from '../components/ui/Bits'
import { ForecastChart } from '../charts/charts'
import { bandFor, aqiDisplay, fmtDateLong } from '../utils/aqi'
import { downloadForecastReport } from '../utils/report'
import './dash-pages.css'

export default function ForecastPage() {
  const { state, area } = useSelection()
  const { data, loading, error, refetch } = useApi(
    () => aqiApi.forecast(state, area), [state, area], { enabled: !!(state && area) })
  const cur = useApi(() => aqiApi.current(state, area), [state, area], { enabled: !!(state && area) })
  const [downloading, setDownloading] = useState(false)

  if (!state || !area) return <Loader />
  if (loading) return <Loader label="Loading forecast…" />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  const curBand = cur.data?.available ? bandFor(cur.data.AQI) : null

  const onDownload = async () => {
    setDownloading(true)
    try { downloadForecastReport({ state, area, current: cur.data, forecast: data }) }
    finally { setDownloading(false) }
  }

  if (!data.forecast_available) {
    return (
      <div>
        <div className="page-head page-head-row">
          <div>
            <h1>7-Day AQI Forecast</h1>
            <p>AI-powered air-quality predictions for the next seven days.</p>
          </div>
        </div>
        <EmptyState title="No forecast for this area yet" hint={data.reason} />
      </div>
    )
  }

  return (
    <div>
      <div className="page-head page-head-row">
        <div>
          <h1>7-Day AQI Forecast</h1>
          <p>AI-powered air-quality predictions for the next seven days — {area}, {state}.</p>
        </div>
        <button className="btn btn-ghost" onClick={onDownload} disabled={downloading}>
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
        <div className="fc-status-chip">
          <span className="fc-status-label">◆ 7-DAY FORECAST · PREDICTED · SMART AQI {data.model}</span>
        </div>
      </div>

      <div className="banner">{data.note} {data.method ? `Method: ${data.method}.` : ''}
        {' '}Generated {fmtDateLong(data.generated_at)}. Horizon (+1d…+7d) counts forward from this
        station's own last data point, which can lag today's calendar date — treat +1d…+7d as the
        reliable label, not the printed date.</div>

      <GlassCard className="card" style={{ marginBottom: 18 }}>
        <SectionTitle eyebrow="Interactive 3D" title="Forecast ribbon" />
        <div className="canvas-box tall">
          <SceneCanvas camera={{ position: [0, 1.6, 8], fov: 46 }} style={{ width: '100%', height: '100%' }}
            fallback={<div />}>
            <ForecastRibbon days={data.days} />
          </SceneCanvas>
        </div>
        <div className="card-note">Drag to rotate · scroll to zoom · whiskers show the uncertainty band</div>
      </GlassCard>

      <div className="grid g-2">
        <GlassCard className="card">
          <SectionTitle eyebrow="2D" title="Predicted AQI with band" />
          <ForecastChart days={data.days} height={280} />
        </GlassCard>
        <GlassCard className="card">
          <SectionTitle title="Day by day" />
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Horizon</th><th>AQI</th><th>Category</th><th>Range</th></tr></thead>
              <tbody>
                {data.days.map((d) => {
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
    </div>
  )
}
