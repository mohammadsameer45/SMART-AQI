import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { aqi as aqiApi } from '../api/endpoints'
import AQIGauge from '../components/AQIGauge'
import { GlassCard, StatTile, Loader, ErrorState, AQIChip, SectionTitle } from '../components/ui/Bits'
import { HistoryChart, ForecastChart } from '../charts/charts'
import WeatherCard from '../components/WeatherCard'
import { bandFor, fmtDateLong } from '../utils/aqi'
import './dash-pages.css'

export default function DashboardHome() {
  const { state, area } = useSelection()
  const { data, loading, error, refetch } = useApi(
    () => aqiApi.dashboard(state, area), [state, area], { enabled: !!(state && area) })

  if (!state || !area) return <Loader label="Loading locations…" />
  if (loading) return <Loader label="Loading dashboard…" />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  const cur = data.current
  const band = bandFor(cur?.AQI)
  const fc = data.forecast
  const adv = data.advisory

  return (
    <div>
      <div className="page-head">
        <h1>Overview</h1>
        <p>{area}, {state}{cur?.available ? ` · as of ${fmtDateLong(cur.as_of)}` : ''}</p>
      </div>

      {cur?.available && !cur.is_live && (
        <div className="banner">{cur.source_note}</div>
      )}
      {cur?.is_live && data.live_refresh?.running && (
        <div className="tiny muted" style={{ marginBottom: 14 }}>
          ● Live CPCB feed · refreshed {data.live_refresh.age_minutes} min ago
          {data.live_refresh.age_minutes > 90 ? ' (worker may be stopped)' : ''}
        </div>
      )}

      <div className="grid g-hero" style={{ marginBottom: 18 }}>
        <GlassCard className="gauge-card">
          <AQIGauge value={cur?.available ? cur.AQI : null} />
          <div className="gauge-meta">
            <div className="loc">{area}</div>
            {band && <AQIChip label={band.label} color={band.hex} />}
          </div>
        </GlassCard>

        <div className="grid g-2">
          <StatTile label="PM2.5" value={fmtNum(cur?.pollutants?.PM25)} sub="µg/m³" />
          <StatTile label="PM10" value={fmtNum(cur?.pollutants?.PM10)} sub="µg/m³" />
          <StatTile label="NO₂" value={fmtNum(cur?.pollutants?.NO2)} sub="µg/m³" />
          <StatTile label="O₃" value={fmtNum(cur?.pollutants?.O3)} sub="µg/m³" />
          <StatTile label="Stations" value={data.coverage?.n_stations ?? '—'}
            sub={`${data.coverage?.matched_level} level`} />
          <StatTile label="Records" value={(data.coverage?.total_records ?? 0).toLocaleString()}
            sub={`through ${data.coverage?.history_end || '—'}`} />
        </div>
      </div>

      <div className="grid g-2">
        <GlassCard className="card">
          <SectionTitle eyebrow="Last 90 days" title="AQI history" />
          <HistoryChart series={data.history_90d} />
        </GlassCard>

        <GlassCard className="card">
          <SectionTitle eyebrow="Next 7 days" title="AQI forecast" />
          {fc?.forecast_available
            ? <>
                <ForecastChart days={fc.days} />
                <div className="card-note">Model: {fc.model} · predictions, not measurements</div>
              </>
            : <p className="muted tiny">{fc?.reason || 'No forecast for this area.'}</p>}
        </GlassCard>
      </div>

      {data.weather && (
        <div style={{ marginTop: 18 }}><WeatherCard weather={data.weather} /></div>
      )}

      {adv?.available && (
        <GlassCard className="card advisory-card" style={{ marginTop: 18, '--c': band?.hex }}>
          <SectionTitle eyebrow="Health advisory" title={adv.air_quality_status || 'Guidance'} />
          <div className="grid g-2">
            <div>
              <b className="tiny muted">Outdoor activity</b>
              <p style={{ fontSize: 13.5, marginTop: 4 }}>{adv.outdoor_activity}</p>
            </div>
            <div>
              <b className="tiny muted">Respiratory precautions</b>
              <ul className="advisory-list">
                {(adv.respiratory_precautions || []).slice(0, 3).map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </div>
          </div>
          <div className="disclaimer">{adv.disclaimer}</div>
        </GlassCard>
      )}
    </div>
  )
}

const fmtNum = (v) => (v == null ? '—' : Math.round(v))
