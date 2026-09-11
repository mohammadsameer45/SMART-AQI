import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { aqiColor, aqiDisplay, aqiLabel } from '../utils/aqi'
import './forecast-teaser.css'

/**
 * Premium animated ribbon promoting the dedicated Forecast tab. Purely a
 * teaser — the authoritative 7-day numbers live on /app/forecast (via the
 * real forecast API); this reads the same already-fetched `days` so nothing
 * here is invented.
 */
export default function ForecastTeaser({ days = [], model, available = true, reason }) {
  if (!available || !days.length) {
    return (
      <motion.div className="fc-teaser fc-teaser-empty"
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}>
        <div className="fc-teaser-empty-inner">
          <span className="fc-eyebrow">◆ PREDICTED</span>
          <p>{reason || 'No 7-day forecast available for this area yet.'}</p>
        </div>
      </motion.div>
    )
  }

  const first = days[0].predicted_AQI
  const last = days[days.length - 1].predicted_AQI
  const trend = last - first
  const trendDir = trend > 4 ? 'up' : trend < -4 ? 'down' : 'flat'
  const maxV = Math.max(...days.map((d) => d.predicted_AQI), 10)
  const minV = Math.min(...days.map((d) => d.predicted_AQI), 0)
  const span = Math.max(maxV - minV, 1)

  const W = 320, H = 64, PAD = 6
  const pt = (i, v) => {
    const frac = days.length > 1 ? i / (days.length - 1) : 0.5
    const x = PAD + frac * (W - PAD * 2)
    const y = H - PAD - ((v - minV) / span) * (H - PAD * 2)
    return [x, y]
  }
  const linePath = days.map((d, i) => pt(i, d.predicted_AQI))
    .map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const areaPath = `${linePath} L${W - PAD},${H} L${PAD},${H} Z`

  return (
    <motion.div className="fc-teaser"
      initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}>
      <div className="fc-teaser-glow" aria-hidden="true" />
      <div className="fc-teaser-sheen" aria-hidden="true" />

      <div className="fc-teaser-body">
        <div className="fc-teaser-head">
          <div>
            <span className="fc-eyebrow">◆ PREDICTED · 7-DAY FORECAST</span>
            <h3>SMART AQI can see the week ahead</h3>
          </div>
          <span className={`fc-trend fc-trend-${trendDir}`}>
            {trendDir === 'up' ? '▲' : trendDir === 'down' ? '▼' : '►'}
            {' '}{Math.abs(Math.round(trend))} pts
          </span>
        </div>

        <div className="fc-teaser-chart">
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="fc-spark">
            <defs>
              <linearGradient id="fc-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--violet-400)" stopOpacity="0.35" />
                <stop offset="100%" stopColor="var(--violet-400)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d={areaPath} fill="url(#fc-area)" className="fc-spark-area" />
            <path d={linePath} className="fc-spark-line" />
            {days.map((d, i) => {
              const [x, y] = pt(i, d.predicted_AQI)
              return <circle key={i} cx={x} cy={y} r={2.6} fill={aqiColor(d.predicted_AQI)}
                className="fc-spark-dot" style={{ animationDelay: `${0.4 + i * 0.08}s` }} />
            })}
          </svg>

          <div className="fc-teaser-days">
            {days.map((d, i) => (
              <div key={i} className="fc-day" style={{ animationDelay: `${0.5 + i * 0.06}s` }}>
                <span className="fc-day-dot" style={{ background: aqiColor(d.predicted_AQI) }} />
                <span className="fc-day-v">{aqiDisplay(d.predicted_AQI)}</span>
                <span className="fc-day-l tiny muted">{aqiLabel(d.predicted_AQI)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="fc-teaser-foot">
          <span className="tiny muted">Model: {model || '—'} · predictions, not measurements</span>
          <Link to="/app/forecast" className="btn btn-primary fc-teaser-cta">
            Open full forecast →
          </Link>
        </div>
      </div>
    </motion.div>
  )
}
