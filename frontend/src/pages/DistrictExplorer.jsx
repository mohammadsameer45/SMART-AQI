import { useSelection } from '../components/SelectionContext'
import AreaPicker from '../components/AreaPicker'
import { useApi } from '../hooks/useApi'
import { aqi as aqiApi, geo } from '../api/endpoints'
import AQIGauge from '../components/AQIGauge'
import { GlassCard, Loader, ErrorState, EmptyState, AQIChip, SectionTitle, StatTile } from '../components/ui/Bits'
import { HistoryChart, ForecastChart, HeatCalendar, MonthlyTrend } from '../charts/charts'
import WeatherCard from '../components/WeatherCard'
import { bandFor, fmtDate, fmtDateLong } from '../utils/aqi'
import './dash-pages.css'

export default function DistrictExplorer() {
  const { state, area } = useSelection()
  const enabled = !!(state && area)
  const dash = useApi(() => aqiApi.dashboard(state, area), [state, area], { enabled })
  const locs = useApi(() => geo.locations(state, area), [state, area], { enabled })
  const cal = useApi(() => aqiApi.calendar(state, area), [state, area], { enabled })

  return (
    <div>
      <div className="page-head">
        <h1>District Explorer</h1>
        <p>Drill from state to area. Only areas with legitimate cleaned data appear.</p>
      </div>

      <GlassCard className="card" style={{ marginBottom: 18 }}>
        <AreaPicker />
      </GlassCard>

      {!state || !area ? <Loader />
        : dash.loading ? <Loader label={`Loading ${area}…`} />
        : dash.error ? <ErrorState error={dash.error} onRetry={dash.refetch} />
        : <Explorer dash={dash.data} locs={locs.data} cal={cal} state={state} area={area} />}
    </div>
  )
}

function Explorer({ dash, locs, cal, state, area }) {
  const cur = dash.current
  const band = bandFor(cur?.AQI)
  const cov = dash.coverage
  const fc = dash.forecast

  return (
    <>
      <div className="grid g-4" style={{ marginBottom: 18 }}>
        <StatTile label="Match level" value={cov?.matched_level} />
        <StatTile label="Stations" value={cov?.n_stations ?? '—'} />
        <StatTile label="Records" value={(cov?.total_records ?? 0).toLocaleString()} />
        <StatTile label="Coverage" value={cov?.history_start ? `${cov.history_start.slice(0, 4)}–${cov.history_end?.slice(0, 4)}` : '—'} />
      </div>

      <div className="grid g-hero" style={{ marginBottom: 18 }}>
        <GlassCard className="gauge-card">
          <AQIGauge value={cur?.available ? cur.AQI : null} size={230} />
          {band && <AQIChip label={band.label} color={band.hex} />}
          <div className="tiny muted">{cur?.available ? `as of ${fmtDateLong(cur.as_of)}` : 'no current value'}</div>
        </GlassCard>
        <GlassCard className="card">
          <h3>Pollutants</h3>
          {cur?.pollutants && Object.entries(cur.pollutants).map(([k, v]) => (
            <div className="kv" key={k}><span>{k}</span><span>{v == null ? '—' : Math.round(v)}</span></div>
          ))}
        </GlassCard>
      </div>

      <div className="grid g-2" style={{ marginBottom: 18 }}>
        <GlassCard className="card">
          <SectionTitle eyebrow="Last 90 days" title="History" />
          <HistoryChart series={dash.history_90d} />
        </GlassCard>
        <GlassCard className="card">
          <SectionTitle eyebrow="Next 7 days" title="Forecast" />
          {fc?.forecast_available ? <ForecastChart days={fc.days} />
            : <EmptyState title="No forecast" hint={fc?.reason} />}
        </GlassCard>
      </div>

      {dash.weather && (
        <div style={{ marginBottom: 18 }}><WeatherCard weather={dash.weather} /></div>
      )}

      {locs?.locations?.length > 0 && (
        <GlassCard className="card">
          <SectionTitle title={`${locs.locations.length} monitoring locations`} />
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Level</th><th>City</th><th>Station</th><th>Records</th><th>Coverage</th></tr></thead>
              <tbody>
                {locs.locations.map((l, i) => (
                  <tr key={i}>
                    <td>{l.level}</td><td>{l.city}</td><td>{l.station || '—'}</td>
                    <td>{(l.n_records || 0).toLocaleString()}</td>
                    <td className="tiny muted">{l.history_start} → {l.history_end}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      <AqiCalendarCard cal={cal} />
    </>
  )
}

function AqiCalendarCard({ cal }) {
  return (
    <GlassCard className="card" style={{ marginTop: 18 }}>
      <SectionTitle eyebrow="2015–2020 recorded daily AQI" title="AQI history calendar" />
      {cal.loading ? <Loader /> : cal.error ? <ErrorState error={cal.error} onRetry={cal.refetch} />
        : !cal.data?.available ? (
          <p className="tiny muted">{cal.data?.reason || 'No historical daily series for this area.'}</p>
        ) : (
          <>
            <p className="tiny muted" style={{ marginBottom: 12 }}>
              {cal.data.n_days.toLocaleString()} recorded days · {fmtDate(cal.data.start)} → {fmtDate(cal.data.end)}
            </p>
            <HeatCalendar days={cal.data.days} />
            <div className="grid g-2" style={{ marginTop: 18 }}>
              <div>
                <div className="why-label">Worst month on record</div>
                {cal.data.worst_month
                  ? <p className="tiny">{cal.data.worst_month.month} · avg AQI {cal.data.worst_month.avg_AQI}</p>
                  : <p className="tiny muted">—</p>}
                <div className="why-label" style={{ marginTop: 10 }}>Best month on record</div>
                {cal.data.best_month
                  ? <p className="tiny">{cal.data.best_month.month} · avg AQI {cal.data.best_month.avg_AQI}</p>
                  : <p className="tiny muted">—</p>}
              </div>
              {cal.data.monthly?.length > 1 && (
                <MonthlyTrend data={cal.data.monthly.map((m) => ({ month: m.month, aqi: m.avg_AQI }))} height={140} />
              )}
            </div>
            <p className="card-note">{cal.data.note}</p>
          </>
        )}
    </GlassCard>
  )
}
