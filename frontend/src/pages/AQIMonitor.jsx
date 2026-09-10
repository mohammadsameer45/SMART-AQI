import { useState } from 'react'
import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { aqi as aqiApi } from '../api/endpoints'
import AQIGauge from '../components/AQIGauge'
import { GlassCard, Loader, ErrorState, AQIChip, SectionTitle } from '../components/ui/Bits'
import { HistoryChart } from '../charts/charts'
import { bandFor, aqiColor, fmtDateLong } from '../utils/aqi'
import './dash-pages.css'

const RANGES = [['3M', 90], ['6M', 182], ['1Y', 365], ['All', 4000]]

export default function AQIMonitor() {
  const { state, area } = useSelection()
  const [days, setDays] = useState(182)

  const cur = useApi(() => aqiApi.current(state, area), [state, area], { enabled: !!(state && area) })
  const hist = useApi(() => {
    const to = new Date('2020-07-01')
    const from = new Date(to.getTime() - days * 864e5)
    return aqiApi.history(state, area, { from: iso(from), to: iso(to) })
  }, [state, area, days], { enabled: !!(state && area) })

  if (!state || !area) return <Loader />
  if (cur.loading) return <Loader label="Loading AQI…" />
  if (cur.error) return <ErrorState error={cur.error} onRetry={cur.refetch} />

  const c = cur.data
  const band = bandFor(c?.AQI)

  return (
    <div>
      <div className="page-head">
        <h1>AQI Monitor</h1>
        <p>{area}, {state}{c?.available ? ` · as of ${fmtDateLong(c.as_of)}` : ''}</p>
      </div>

      <div className="grid g-hero" style={{ marginBottom: 18 }}>
        <GlassCard className="gauge-card">
          <AQIGauge value={c?.available ? c.AQI : null} size={240} />
          {band && <AQIChip label={band.label} color={band.hex} />}
        </GlassCard>
        <GlassCard className="card">
          <h3>Pollutant snapshot</h3>
          {c?.pollutants && Object.entries(c.pollutants).map(([k, v]) => (
            <div className="kv" key={k}>
              <span>{k}</span><span>{v == null ? '—' : `${Math.round(v)} ${k === 'CO' ? 'mg/m³' : 'µg/m³'}`}</span>
            </div>
          ))}
        </GlassCard>
      </div>

      {c?.stations?.length > 0 && (
        <GlassCard className="card" style={{ marginBottom: 18 }}>
          <SectionTitle eyebrow="On the latest date" title={`${c.stations.length} monitoring stations`} />
          <div className="table-scroll">
            <table className="table">
              <thead><tr><th>Station</th><th>AQI</th><th>Category</th></tr></thead>
              <tbody>
                {c.stations.map((s) => (
                  <tr key={s.station_id}>
                    <td>{s.station}</td>
                    <td style={{ color: aqiColor(s.AQI), fontWeight: 600 }}>{s.AQI == null ? '—' : Math.round(s.AQI)}</td>
                    <td>{s.AQI_bucket || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      <GlassCard className="card">
        <SectionTitle eyebrow="History" title="AQI over time" right={
          <div className="range-toggle">
            {RANGES.map(([l, d]) => (
              <button key={l} className={days === d ? 'on' : ''} onClick={() => setDays(d)}>{l}</button>
            ))}
          </div>
        } />
        {hist.loading ? <Loader /> : hist.error ? <ErrorState error={hist.error} />
          : <HistoryChart series={hist.data.series} height={300} />}
        <div className="card-note">{hist.data?.count ?? 0} daily points</div>
      </GlassCard>
    </div>
  )
}

const iso = (d) => d.toISOString().slice(0, 10)
