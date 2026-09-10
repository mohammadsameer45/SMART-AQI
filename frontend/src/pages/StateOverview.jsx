import { useNavigate } from 'react-router-dom'
import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { geo } from '../api/endpoints'
import AQIGauge from '../components/AQIGauge'
import { GlassCard, Loader, ErrorState, StatTile, AQIChip, SectionTitle } from '../components/ui/Bits'
import { DistributionBar, MonthlyTrend } from '../charts/charts'
import { bandFor } from '../utils/aqi'
import './dash-pages.css'

export default function StateOverview() {
  const { states, state, setState, setArea } = useSelection()
  const nav = useNavigate()
  const { data, loading, error, refetch } = useApi(
    () => geo.overview(state), [state], { enabled: !!state })

  const goDistrict = (d) => { setArea(d); nav('/app/explorer') }

  return (
    <div>
      <div className="page-head">
        <h1>State Overview</h1>
        <p>Every state represented in the cleaned dataset — averages, distribution and district rankings.</p>
      </div>

      <GlassCard className="card" style={{ marginBottom: 18 }}>
        <label className="ap-field" style={{ maxWidth: 260 }}>
          <span>State</span>
          <select value={state} onChange={(e) => setState(e.target.value)}>
            {states.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </GlassCard>

      {!state ? <Loader />
        : loading ? <Loader label={`Loading ${state}…`} />
        : error ? <ErrorState error={error} onRetry={refetch} />
        : <Body data={data} goDistrict={goDistrict} />}
    </div>
  )
}

function Body({ data, goDistrict }) {
  const curr = data.current
  const cband = bandFor(curr?.aqi)
  const aband = bandFor(data.avg_aqi)

  return (
    <>
      <div className="grid g-hero" style={{ marginBottom: 18 }}>
        <GlassCard className="gauge-card">
          <AQIGauge value={curr ? curr.aqi : null} size={230} />
          {cband && <AQIChip label={`Current · ${cband.label}`} color={cband.hex} />}
          <div className="tiny muted">
            {curr?.source === 'live' ? `live · ${curr.n_stations} stations`
              : curr?.as_of ? `latest available · ${curr.as_of}` : 'no current reading'}
          </div>
        </GlassCard>

        <div className="grid g-2">
          <StatTile label="Average AQI" value={data.avg_aqi ?? '—'}
            sub={data.avg_bucket} accent={aband?.hex} />
          <StatTile label="Districts with data" value={data.n_districts} />
          <StatTile label="Monitoring stations" value={data.n_stations} />
          <StatTile label="Observations" value={(data.records ?? 0).toLocaleString()}
            sub={data.coverage?.from ? `${data.coverage.from} → ${data.coverage.to}` : ''} />
        </div>
      </div>

      <GlassCard className="card" style={{ marginBottom: 18 }}>
        <SectionTitle eyebrow="Station-days by category" title="AQI distribution" />
        <DistributionBar data={data.distribution} />
        <div className="map-legend" style={{ marginTop: 12 }}>
          {data.distribution.map((d) => (
            <span key={d.bucket} className="ml-item">
              <span className="ml-sw" style={{ background: d.color }} /> {d.bucket} · {d.pct}%
            </span>
          ))}
        </div>
      </GlassCard>

      <div className="grid g-2" style={{ marginBottom: 18 }}>
        <GlassCard className="card">
          <SectionTitle title="Best-performing districts" eyebrow="lowest average AQI" />
          <DistrictList rows={data.best_districts} onPick={goDistrict} />
        </GlassCard>
        <GlassCard className="card">
          <SectionTitle title="Worst-performing districts" eyebrow="highest average AQI" />
          <DistrictList rows={data.worst_districts} onPick={goDistrict} />
        </GlassCard>
      </div>

      <GlassCard className="card">
        <SectionTitle eyebrow="Monthly mean, all stations" title="AQI trend" />
        {data.monthly_trend?.length
          ? <MonthlyTrend data={data.monthly_trend} height={280} />
          : <p className="muted tiny">Not enough history for a trend.</p>}
      </GlassCard>
    </>
  )
}

function DistrictList({ rows = [], onPick }) {
  if (!rows.length) return <p className="muted tiny">No districted stations in this state yet.</p>
  return (
    <div className="table-scroll">
      <table className="table">
        <thead><tr><th>District</th><th>Avg AQI</th><th>Current</th><th>Stations</th></tr></thead>
        <tbody>
          {rows.map((r) => {
            const b = bandFor(r.avg_aqi)
            return (
              <tr key={r.district} style={{ cursor: 'pointer' }} onClick={() => onPick(r.district)}>
                <td>{r.district}</td>
                <td style={{ color: b?.hex, fontWeight: 700 }}>{r.avg_aqi ?? '—'}</td>
                <td>{r.current_aqi != null
                  ? <AQIChip label={String(r.current_aqi)} color={bandFor(r.current_aqi)?.hex} />
                  : '—'}</td>
                <td>{r.n_stations}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
