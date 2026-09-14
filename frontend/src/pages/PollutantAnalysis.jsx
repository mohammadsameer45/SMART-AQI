import { useState } from 'react'
import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { aqi as aqiApi, weather as weatherApi } from '../api/endpoints'
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
  const enabled = !!(state && area)
  const pol = useApi(() => aqiApi.pollutants(state, area), [state, area], { enabled })
  const hist = useApi(() => aqiApi.history(state, area, { from: '2020-01-01', to: '2020-07-01' }),
    [state, area], { enabled })
  const trend = useApi(() => aqiApi.trend(state, area), [state, area], { enabled })
  const explain = useApi(() => aqiApi.explanation(state, area), [state, area], { enabled })
  const impact = useApi(() => aqiApi.impact(state, area), [state, area], { enabled })
  const disp = useApi(() => weatherApi.dispersion(state, area), [state, area], { enabled })

  const [whyFor, setWhyFor] = useState(null)
  const why = useApi(() => aqiApi.pollutantWhy(state, area, whyFor), [state, area, whyFor],
    { enabled: enabled && !!whyFor })

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
        <p>{area}, {state} · {pol.data.is_live ? 'live CPCB reading' : `${pol.data.as_of} · historical`}</p>
      </div>

      <WhyAqiHigh explain={explain} trend={trend} disp={disp} />

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
        {items.map((p) => {
          const ch = p.change_24h
          const rising = ch && ch.pct != null && ch.pct > 0
          const open = whyFor === p.pollutant
          return (
            <GlassCard key={p.pollutant} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <h3>{p.pollutant.replace('25', '2.5')}</h3>
                {ch && ch.pct != null && (
                  <span className={`chg-badge ${rising ? 'up' : 'down'}`}>
                    {rising ? '↑' : '↓'} {Math.abs(ch.pct)}%
                  </span>
                )}
              </div>
              <div className="stat-value" style={{ color: COLORS[p.pollutant] }}>
                {p.current == null ? '—' : Math.round(p.current)} <span className="tiny muted">{p.unit}</span>
              </div>
              {p.live_feed_note ? (
                <p className="card-note">{p.live_feed_note}</p>
              ) : (
                <>
                  <div className="kv"><span>{p.trend_days ? `${p.trend_days}d mean` : 'recent mean'}</span><span>{fmt(p.trend_mean)}</span></div>
                  <div className="kv"><span>min / max</span><span>{fmt(p.trend_min)} / {fmt(p.trend_max)}</span></div>
                </>
              )}
              <p className="card-note">{p.health_relevance}</p>
              <div className="pill-row">
                {p.possible_source_categories.slice(0, 3).map((s) => (
                  <span key={s} className="src-chip">{s}</span>
                ))}
              </div>
              {p.current != null && (
                <button className="btn btn-ghost why-btn" onClick={() => setWhyFor(open ? null : p.pollutant)}>
                  {open ? 'Hide' : '[WHY?]'}
                </button>
              )}
              {open && (
                <div className="why-panel">
                  {why.loading ? <Loader label="Checking evidence…" /> : why.error ? (
                    <p className="tiny muted">Couldn't load — try again.</p>
                  ) : why.data && !why.data.available ? (
                    <p className="tiny muted">{why.data.reason}</p>
                  ) : why.data ? (
                    <>
                      <p className="tiny">{why.data.observed}</p>
                      {why.data.possible_contributors_evidence_based.length > 0 && (
                        <>
                          <div className="why-label">Possible contributor (evidence-based)</div>
                          {why.data.possible_contributors_evidence_based.map((c) => (
                            <div key={c.factor} className="why-item">
                              <strong>{c.factor}</strong>
                              <p className="tiny muted">{c.evidence}</p>
                            </div>
                          ))}
                        </>
                      )}
                      <div className="why-label">Typical sources of {p.pollutant.replace('25', '2.5')} (general)</div>
                      <div className="pill-row">
                        {why.data.possible_source_categories_general.map((s) => (
                          <span key={s} className="src-chip">{s}</span>
                        ))}
                      </div>
                      <p className="card-note">{why.data.disclaimer}</p>
                    </>
                  ) : null}
                </div>
              )}
            </GlassCard>
          )
        })}
      </div>

      <div className="grid g-2" style={{ marginBottom: 18 }}>
        <SourceAnalysisCard state={state} area={area} enabled={enabled} />
        <ImpactBreakdownCard impact={impact} />
      </div>

      <GlassCard className="card">
        <SectionTitle eyebrow="H1 2020" title="Pollutant trends" />
        {hist.loading ? <Loader /> : hist.error ? <ErrorState error={hist.error} />
          : hist.data.series.length === 0
            ? <p className="tiny muted">No historical (2015–2020) series for this area — it's covered only by the live CPCB feed.</p>
            : <PollutantTrend series={hist.data.series} keys={['PM25', 'PM10', 'NO2', 'O3']} height={280} />}
      </GlassCard>
    </div>
  )
}

function WhyAqiHigh({ explain, trend, disp }) {
  return (
    <GlassCard className="card" style={{ marginBottom: 18 }}>
      <SectionTitle eyebrow="Diagnostics" title="Why is AQI like this?" />
      <div className="grid g-3">
        <div>
          <div className="why-label">Trend vs previous reading</div>
          {trend.loading ? <Loader /> : !trend.data?.available ? (
            <p className="tiny muted">{trend.data?.reason || 'Not enough data yet.'}</p>
          ) : (
            <>
              <div className="trend-line">
                <span style={{ fontSize: 20 }}>{trend.data.emoji}</span>
                <span className="stat-value" style={{ fontSize: 20 }}>
                  {trend.data.absolute_change > 0 ? '+' : ''}{trend.data.absolute_change}
                </span>
                <span className="tiny muted">({trend.data.percent_change != null ? `${trend.data.percent_change}%` : '—'})</span>
              </div>
              <p className="tiny muted">{trend.data.category_change} · {trend.data.classification}</p>
              {trend.data.main_pollutant_change && (
                <p className="tiny muted">Main mover: {trend.data.main_pollutant_change.pollutant}</p>
              )}
            </>
          )}
        </div>
        <div>
          <div className="why-label">Spike check</div>
          {explain.loading ? <Loader /> : !explain.data?.available ? (
            <p className="tiny muted">{explain.data?.reason || 'Unavailable.'}</p>
          ) : explain.data.spike?.available ? (
            explain.data.spike.spike_detected ? (
              <p className="spike-alert">⚠️ Abnormal pollution spike detected</p>
            ) : (
              <p className="tiny muted">No abnormal spike detected (z={explain.data.spike.z_score ?? '—'}).</p>
            )
          ) : (
            <p className="tiny muted">{explain.data.spike?.reason || 'Not enough live history yet.'}</p>
          )}
        </div>
        <div>
          <div className="why-label">Wind / dispersion</div>
          {disp.loading ? <Loader /> : !disp.data?.available ? (
            <p className="tiny muted">{disp.data?.reason || 'Weather unavailable.'}</p>
          ) : (
            <>
              <div className="stat-value" style={{ fontSize: 20 }}>{disp.data.wind_speed_kmh} km/h</div>
              <p className="tiny muted">{disp.data.wind_direction} · dispersion: {disp.data.dispersion_condition}</p>
            </>
          )}
        </div>
      </div>
      {explain.data?.available && (
        <p className="card-note" style={{ marginTop: 14 }}>{explain.data.summary}</p>
      )}
      {explain.data?.available && explain.data.rising_pollutants_24h.length > 0 && (
        <div className="pill-row" style={{ marginTop: 8 }}>
          {explain.data.rising_pollutants_24h.map((r) => (
            <span key={r.pollutant} className="src-chip up">{r.pollutant} ↑{r.change_24h_pct}%</span>
          ))}
        </div>
      )}
    </GlassCard>
  )
}

function SourceAnalysisCard({ state, area, enabled }) {
  const src = useApi(() => aqiApi.sourceAnalysis(state, area), [state, area], { enabled })
  return (
    <GlassCard className="card">
      <SectionTitle eyebrow="Heuristic" title="Possible source analysis" />
      {src.loading ? <Loader /> : !src.data?.available ? (
        <p className="tiny muted">{src.data?.reason || 'Unavailable.'}</p>
      ) : src.data.ranked.length === 0 ? (
        <p className="tiny muted">No pollutants notably elevated in the last 24h.</p>
      ) : (
        <>
          {src.data.ranked.map((r) => (
            <div key={r.category} className="kv" style={{ display: 'block', border: 'none', padding: '8px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{r.category}</span><span className="tiny muted">{r.based_on.join(', ')}</span>
              </div>
              <div className="imp-bar"><span style={{ width: `${Math.min(r.score * 33, 100)}%` }} /></div>
            </div>
          ))}
          <p className="card-note">{src.data.note}</p>
        </>
      )}
    </GlassCard>
  )
}

function ImpactBreakdownCard({ impact }) {
  return (
    <GlassCard className="card">
      <SectionTitle eyebrow={impact.data?.label || 'Heuristic'} title="Pollutant impact" />
      {impact.loading ? <Loader /> : !impact.data?.available ? (
        <p className="tiny muted">{impact.data?.reason || 'Unavailable.'}</p>
      ) : (
        <>
          {impact.data.bars.map((b) => (
            <div key={b.pollutant} className="kv" style={{ display: 'block', border: 'none', padding: '8px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{b.pollutant.replace('25', '2.5')}</span>
                <span className="tiny muted">{b.relative_share_pct}%</span>
              </div>
              <div className="imp-bar"><span style={{ width: `${b.relative_share_pct}%`, background: COLORS[b.pollutant] }} /></div>
            </div>
          ))}
          <p className="card-note">{impact.data.note}</p>
        </>
      )}
    </GlassCard>
  )
}

const fmt = (v) => (v == null ? '—' : Math.round(v))
