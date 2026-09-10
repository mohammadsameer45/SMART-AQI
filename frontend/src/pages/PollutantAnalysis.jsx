import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { aqi as aqiApi } from '../api/endpoints'
import SceneCanvas from '../three/SceneCanvas'
import PollutantColumns from '../three/PollutantColumns'
import { GlassCard, Loader, ErrorState, SectionTitle } from '../components/ui/Bits'
import { PollutantTrend } from '../charts/charts'
import './dash-pages.css'

const COLORS = {
  PM25: '#a78bfa', PM10: '#f0c030', NO2: '#38bdf8', SO2: '#e24b4b',
  CO: '#f08b24', O3: '#2e9e4f', NO: '#7bb93f', NOx: '#8b5cf6', NH3: '#c084fc',
}

export default function PollutantAnalysis() {
  const { state, area } = useSelection()
  const pol = useApi(() => aqiApi.pollutants(state, area), [state, area], { enabled: !!(state && area) })
  const hist = useApi(() => aqiApi.history(state, area, { from: '2020-01-01', to: '2020-07-01' }),
    [state, area], { enabled: !!(state && area) })

  if (!state || !area) return <Loader />
  if (pol.loading) return <Loader label="Loading pollutants…" />
  if (pol.error) return <ErrorState error={pol.error} onRetry={pol.refetch} />
  if (!pol.data.available) return <ErrorState error={{ message: pol.data.reason }} />

  const items = pol.data.pollutants
  const cols = items.map((p) => ({ label: p.pollutant.replace('25', '2.5'), value: p.current, color: COLORS[p.pollutant] }))

  return (
    <div>
      <div className="page-head">
        <h1>Pollutant Analysis</h1>
        <p>{area}, {state} · current values and recent {pol.data.trend_days}-day trend</p>
      </div>

      <GlassCard className="card" style={{ marginBottom: 18 }}>
        <SectionTitle eyebrow="Interactive 3D" title="Pollutant columns" />
        <div className="canvas-box tall">
          <SceneCanvas camera={{ position: [0, 2, 9], fov: 46 }} style={{ width: '100%', height: '100%' }} fallback={<div />}>
            <PollutantColumns data={cols} />
          </SceneCanvas>
        </div>
        <div className="card-note">Drag to rotate · bar height = current concentration</div>
      </GlassCard>

      <div className="grid g-3" style={{ marginBottom: 18 }}>
        {items.map((p) => (
          <GlassCard key={p.pollutant} className="card">
            <h3>{p.pollutant.replace('25', '2.5')}</h3>
            <div className="stat-value" style={{ color: COLORS[p.pollutant] }}>
              {p.current == null ? '—' : Math.round(p.current)} <span className="tiny muted">{p.unit}</span>
            </div>
            <div className="kv"><span>{p.trend_days ?? ''}d mean</span><span>{fmt(p.trend_mean)}</span></div>
            <div className="kv"><span>min / max</span><span>{fmt(p.trend_min)} / {fmt(p.trend_max)}</span></div>
            <p className="card-note">{p.health_relevance}</p>
          </GlassCard>
        ))}
      </div>

      <GlassCard className="card">
        <SectionTitle eyebrow="H1 2020" title="Pollutant trends" />
        {hist.loading ? <Loader /> : hist.error ? <ErrorState error={hist.error} />
          : <PollutantTrend series={hist.data.series} keys={['PM25', 'PM10', 'NO2', 'O3']} height={280} />}
      </GlassCard>
    </div>
  )
}
const fmt = (v) => (v == null ? '—' : Math.round(v))
