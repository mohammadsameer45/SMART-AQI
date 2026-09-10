import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import { health as healthApi } from '../api/endpoints'
import { GlassCard, Loader, ErrorState, EmptyState, AQIChip, SectionTitle } from '../components/ui/Bits'
import { bandFor, fmtDateLong } from '../utils/aqi'
import './dash-pages.css'

export default function HealthAdvisory() {
  const { state, area } = useSelection()
  const { data, loading, error, refetch } = useApi(
    () => healthApi.advisory(state, area), [state, area], { enabled: !!(state && area) })

  if (!state || !area) return <Loader />
  if (loading) return <Loader label="Loading advisory…" />
  if (error) return <ErrorState error={error} onRetry={refetch} />
  if (!data.available) return <EmptyState title="No advisory available" hint={data.reason} />

  const band = bandFor(data.current_AQI)
  const t = data.tomorrow_risk
  const wk = data.seven_day_outlook

  return (
    <div>
      <div className="page-head">
        <h1>Health Advisory</h1>
        <p>{area}, {state} · as of {fmtDateLong(data.as_of)} · precautionary guidance, not medical advice</p>
      </div>

      <div className="grid g-3" style={{ marginBottom: 18 }}>
        <GlassCard className="card advisory-card" style={{ '--c': band?.hex }}>
          <h3>Air Quality Status</h3>
          <div className="stat-value" style={{ color: band?.hex }}>{Math.round(data.current_AQI)}</div>
          <AQIChip label={data.current_bucket} color={band?.hex} />
          <p className="card-note">{data.air_quality_status}</p>
        </GlassCard>

        <GlassCard className="card">
          <h3>Who should take extra care?</h3>
          {data.who_should_take_care?.length
            ? <ul className="advisory-list">{data.who_should_take_care.map((w, i) => <li key={i}>{w}</li>)}</ul>
            : <p className="muted tiny">No special precautions needed for the general population.</p>}
        </GlassCard>

        <GlassCard className="card">
          <h3>Outdoor Activity Recommendation</h3>
          <p style={{ fontSize: 14 }}>{data.outdoor_activity}</p>
        </GlassCard>
      </div>

      <div className="grid g-2" style={{ marginBottom: 18 }}>
        <GlassCard className="card">
          <SectionTitle title="Respiratory Precautions" eyebrow="For sensitive groups" />
          <ul className="advisory-list">
            {(data.respiratory_precautions || []).map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </GlassCard>

        <GlassCard className="card">
          <SectionTitle title="Tomorrow's Risk" eyebrow="From the forecast" />
          {t ? (
            <>
              <div className="stat-value" style={{ color: bandFor(t.predicted_AQI)?.hex }}>
                {Math.round(t.predicted_AQI)} <span className="tiny muted">{t.AQI_bucket}</span>
              </div>
              <p className="tiny muted">{fmtDateLong(t.forecast_date)} · air quality {t.direction}</p>
              {t.advisory?.guidance && (
                <ul className="advisory-list">{t.advisory.guidance.slice(0, 3).map((g, i) => <li key={i}>{g}</li>)}</ul>
              )}
            </>
          ) : <p className="muted tiny">No forecast available for this area.</p>}
        </GlassCard>
      </div>

      {wk && (
        <GlassCard className="card" style={{ marginBottom: 18 }}>
          <SectionTitle title="7-Day Health Outlook" />
          <div className="pill-row">
            {wk.buckets.map((b, i) => {
              const bb = bandFor({ Good: 25, Satisfactory: 75, Moderate: 150, Poor: 250, 'Very Poor': 350, Severe: 450 }[b])
              return <AQIChip key={i} label={`+${i + 1}d · ${b}`} color={bb?.hex} />
            })}
          </div>
          <p className="card-note">Worst expected: {wk.worst_bucket} ({Math.round(wk.worst_AQI)}) on {fmtDateLong(wk.worst_day)}</p>
        </GlassCard>
      )}

      <div className="disclaimer">{data.disclaimer}</div>
    </div>
  )
}
