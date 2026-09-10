import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { models as modelsApi } from '../api/endpoints'
import { GlassCard, Loader, ErrorState, SectionTitle, AQIChip } from '../components/ui/Bits'
import { ModelCompareChart, ActualVsPredicted } from '../charts/charts'
import './dash-pages.css'

const METRICS = ['MAE', 'RMSE', 'R2', 'MAPE']

export default function ModelInsights() {
  const mm = useApi(() => modelsApi.metrics(), [])
  const [metric, setMetric] = useState('MAE')
  const [sel, setSel] = useState('baseline')
  const mi = useApi(() => modelsApi.insights(sel), [sel])

  if (mm.loading) return <Loader label="Loading models…" />
  if (mm.error) return <ErrorState error={mm.error} onRetry={mm.refetch} />

  const rows = mm.data.models

  return (
    <div>
      <div className="page-head">
        <h1>Model Insights — AI Forecast Engine</h1>
        <p>{mm.data.note} Best: <b>{mm.data.best_model}</b></p>
      </div>

      <GlassCard className="card" style={{ marginBottom: 18 }}>
        <SectionTitle title="Comparison" eyebrow="Held-out test period (H1 2020)" />
        <div className="table-scroll">
          <table className="table">
            <thead><tr><th>Model</th><th>val MAE</th><th>MAE</th><th>RMSE</th><th>R²</th><th>MAPE %</th><th>Train s</th><th></th></tr></thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.model_name} className={m.is_best ? 'best' : ''}>
                  <td style={{ fontWeight: 600 }}>{m.model_name}</td>
                  <td>{m.val_MAE}</td><td>{m.MAE}</td><td>{m.RMSE}</td>
                  <td>{m.R2}</td><td>{m.MAPE}</td><td>{m.training_time_s}</td>
                  <td>{m.is_best && <AQIChip label="best" color="#8b5cf6" />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <div className="grid g-2" style={{ marginBottom: 18 }}>
        <GlassCard className="card">
          <SectionTitle title="Metric comparison" right={
            <div className="range-toggle">
              {METRICS.map((mt) => (
                <button key={mt} className={metric === mt ? 'on' : ''} onClick={() => setMetric(mt)}>{mt}</button>
              ))}
            </div>
          } />
          <ModelCompareChart models={rows} metric={metric} />
        </GlassCard>

        <GlassCard className="card">
          <SectionTitle title="Actual vs predicted" right={
            <div className="range-toggle">
              {rows.map((m) => (
                <button key={m.model_name} className={sel === m.model_name ? 'on' : ''}
                  onClick={() => setSel(m.model_name)}>{m.model_name}</button>
              ))}
            </div>
          } />
          {mi.loading ? <Loader /> : mi.error ? <ErrorState error={mi.error} />
            : mi.data.actual_vs_predicted
              ? <ActualVsPredicted points={mi.data.actual_vs_predicted} />
              : <p className="muted tiny">{mi.data.avp_note}</p>}
        </GlassCard>
      </div>

      {mi.data?.feature_importance && (
        <GlassCard className="card">
          <SectionTitle title="Feature importance" eyebrow={`${sel} · importance ≠ causation`} />
          {Object.entries(mi.data.feature_importance).slice(0, 10).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 10 }}>
              <div className="kv" style={{ border: 'none', padding: '2px 0' }}>
                <span style={{ color: 'var(--text-1)' }}>{k}</span><span>{(v * 100).toFixed(1)}%</span>
              </div>
              <div className="imp-bar"><span style={{ width: `${Math.min(v * 100 * 1.6, 100)}%` }} /></div>
            </div>
          ))}
        </GlassCard>
      )}
    </div>
  )
}
