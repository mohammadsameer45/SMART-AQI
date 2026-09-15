import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, BarChart, Bar,
  ComposedChart, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, Cell, Legend,
} from 'recharts'
import { aqiColor, aqiLabel, fmtDate, fmtDateLong, AQI_BANDS } from '../utils/aqi'

const AX = { stroke: '#52525b', fontSize: 11 }
const GRID = { stroke: 'rgba(255,255,255,0.06)' }
const tip = {
  contentStyle: {
    background: 'rgba(13,13,21,0.95)', border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 12, fontSize: 12, color: '#fff',
  },
  labelStyle: { color: '#a1a1aa' },
}

export function HistoryChart({ series = [], height = 260 }) {
  const data = series.map((d) => ({ ...d, label: fmtDate(d.date) }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 10, bottom: 0, left: -12 }}>
        <defs>
          <linearGradient id="aqiFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="label" {...AX} minTickGap={28} tickLine={false} axisLine={false} />
        <YAxis {...AX} tickLine={false} axisLine={false} width={40} />
        <Tooltip {...tip} />
        <Area type="monotone" dataKey="AQI" stroke="#a78bfa" strokeWidth={2}
          fill="url(#aqiFill)" connectNulls dot={false} name="AQI" />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function ForecastChart({ days = [], height = 260 }) {
  const data = days.map((d) => ({
    label: `+${d.horizon_day}d`, aqi: d.predicted_AQI,
    lower: d.lower, span: Math.max((d.upper ?? d.predicted_AQI) - (d.lower ?? d.predicted_AQI), 0),
  }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: -12 }} stackOffset="none">
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="label" {...AX} tickLine={false} axisLine={false} />
        <YAxis {...AX} tickLine={false} axisLine={false} width={40} />
        <Tooltip {...tip} />
        {/* uncertainty band drawn as a transparent lower + visible span, stacked */}
        <Area type="monotone" dataKey="lower" stackId="band" stroke="none" fill="none" />
        <Area type="monotone" dataKey="span" stackId="band" stroke="none"
          fill="#7c3aed" fillOpacity={0.16} name="Uncertainty" />
        <Line type="monotone" dataKey="aqi" name="Predicted AQI" stroke="#a78bfa"
          strokeWidth={2.5} dot={{ r: 3, fill: '#fff' }} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

export function Forecast24hChart({ hours = [], height = 240 }) {
  const data = hours.map((h) => ({
    label: h.hour_label, aqi: h.predicted_AQI,
    lower: h.lower, span: h.upper != null && h.lower != null ? Math.max(h.upper - h.lower, 0) : 0,
  }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: -12 }} stackOffset="none">
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="label" {...AX} minTickGap={22} tickLine={false} axisLine={false} />
        <YAxis {...AX} tickLine={false} axisLine={false} width={40} />
        <Tooltip {...tip} />
        <Area type="monotone" dataKey="lower" stackId="band" stroke="none" fill="none" />
        <Area type="monotone" dataKey="span" stackId="band" stroke="none"
          fill="#7c3aed" fillOpacity={0.16} name="Uncertainty" />
        <Line type="monotone" dataKey="aqi" name="Estimated AQI" stroke="#38bdf8"
          strokeWidth={2.5} dot={{ r: 2.5, fill: '#fff' }} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

export function PollutantTrend({ series = [], keys = ['PM25', 'PM10', 'O3'], height = 240 }) {
  const colors = ['#a78bfa', '#f0c030', '#2e9e4f', '#e24b4b', '#38bdf8']
  const data = series.map((d) => ({ ...d, label: fmtDate(d.date) }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="label" {...AX} minTickGap={30} tickLine={false} axisLine={false} />
        <YAxis {...AX} tickLine={false} axisLine={false} width={40} />
        <Tooltip {...tip} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {keys.map((k, i) => (
          <Line key={k} type="monotone" dataKey={k} stroke={colors[i % colors.length]}
            strokeWidth={1.8} dot={false} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

export function ModelCompareChart({ models = [], metric = 'MAE', height = 260 }) {
  const data = models.map((m) => ({ name: m.model_name, value: m[metric], best: m.is_best }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="name" {...AX} tickLine={false} axisLine={false} />
        <YAxis {...AX} tickLine={false} axisLine={false} width={44} />
        <Tooltip {...tip} />
        <Bar dataKey="value" name={metric} radius={[6, 6, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.best ? '#8b5cf6' : '#3f3f56'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function DistributionBar({ data = [], height = 54 }) {
  const total = data.reduce((s, d) => s + d.count, 0) || 1
  return (
    <div style={{ display: 'flex', height, width: '100%', borderRadius: 10, overflow: 'hidden' }}>
      {data.map((d) => (
        d.count > 0 && (
          <div key={d.bucket}
            title={`${d.bucket}: ${d.pct}%`}
            style={{ width: `${(d.count / total) * 100}%`, background: d.color,
                     display: 'grid', placeItems: 'center', fontSize: 10.5,
                     color: '#0b0b0f', fontWeight: 700 }}>
            {d.pct >= 7 ? `${Math.round(d.pct)}%` : ''}
          </div>
        )
      ))}
    </div>
  )
}

export function MonthlyTrend({ data = [], height = 260 }) {
  const rows = data.map((d) => ({ ...d, label: d.month }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 6, right: 12, bottom: 0, left: -12 }}>
        <defs>
          <linearGradient id="stFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.4} />
            <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="label" {...AX} minTickGap={40} tickLine={false} axisLine={false} />
        <YAxis {...AX} tickLine={false} axisLine={false} width={40} />
        <Tooltip {...tip} />
        <Area type="monotone" dataKey="aqi" name="Monthly avg AQI" stroke="#a78bfa"
          strokeWidth={2} fill="url(#stFill)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

const DOW_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', '']
const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function yearWeeks(dayMap, year) {
  const jan1 = new Date(Date.UTC(year, 0, 1))
  const dec31 = new Date(Date.UTC(year, 11, 31))
  const start = new Date(jan1); start.setUTCDate(jan1.getUTCDate() - jan1.getUTCDay())
  const end = new Date(dec31); end.setUTCDate(dec31.getUTCDate() + (6 - dec31.getUTCDay()))

  const weeks = []
  const cur = new Date(start)
  while (cur <= end) {
    const week = []
    for (let i = 0; i < 7; i++) {
      const inYear = cur.getUTCFullYear() === year
      const iso = cur.toISOString().slice(0, 10)
      week.push(inYear ? { date: iso, ...dayMap.get(iso) } : null)
      cur.setUTCDate(cur.getUTCDate() + 1)
    }
    weeks.push(week)
  }
  return weeks
}

function weatherNote(w) {
  if (!w) return ''
  const parts = []
  if (w.temp_mean != null) parts.push(`${w.temp_mean}°C`)
  if (w.humidity != null) parts.push(`${w.humidity}% RH`)
  if (w.wind_mean_ms != null) parts.push(`${w.wind_mean_ms} m/s wind`)
  if (w.rain_mm != null && w.rain_mm > 0) parts.push(`${w.rain_mm} mm rain`)
  return parts.length ? ` · ${parts.join(', ')}` : ''
}

function cellTitle(cell) {
  if (!cell || cell.AQI == null) return cell ? fmtDateLong(cell.date) : ''
  const main = cell.main_pollutant ? ` · main: ${cell.main_pollutant.replace('25', '2.5')}` : ''
  return `${fmtDateLong(cell.date)} · AQI ${Math.round(cell.AQI)} (${cell.AQI_bucket || aqiLabel(cell.AQI)})${main}${weatherNote(cell.weather)}`
}

/** GitHub-contribution-style heat calendar of real recorded daily AQI, one grid per year. */
export function HeatCalendar({ days = [] }) {
  const dayMap = new Map(days.map((d) => [d.date, d]))
  const years = [...new Set(days.map((d) => Number(d.date.slice(0, 4))))].sort((a, b) => b - a)

  return (
    <div className="heat-cal">
      {years.map((year) => {
        const weeks = yearWeeks(dayMap, year)
        let lastMonth = -1
        return (
          <div key={year} className="heat-cal-year">
            <div className="heat-cal-year-label">{year}</div>
            <div className="heat-cal-scroll">
              <div className="heat-cal-dow">
                {DOW_LABELS.map((l, i) => <span key={i}>{l}</span>)}
              </div>
              <div className="heat-cal-grid">
                {weeks.map((week, wi) => {
                  const firstReal = week.find(Boolean)
                  const month = firstReal ? new Date(firstReal.date).getUTCMonth() : lastMonth
                  const showLabel = firstReal && month !== lastMonth
                  if (showLabel) lastMonth = month
                  return (
                    <div key={wi} className="heat-cal-week">
                      <div className="heat-cal-month">{showLabel ? MONTH_LABELS[month] : ''}</div>
                      {week.map((cell, di) => (
                        <div key={di}
                          className={`heat-cal-cell${cell ? '' : ' empty'}`}
                          title={cellTitle(cell)}
                          style={cell?.AQI != null ? { background: aqiColor(cell.AQI) } : undefined} />
                      ))}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )
      })}
      <div className="heat-cal-legend">
        {AQI_BANDS.map((b) => (
          <span key={b.label} className="ml-item">
            <span className="ml-sw" style={{ background: b.hex }} /> {b.label}
          </span>
        ))}
        <span className="ml-item"><span className="ml-sw empty" /> No data</span>
      </div>
    </div>
  )
}

export function ActualVsPredicted({ points = [], height = 300 }) {
  const max = Math.max(...points.flatMap((p) => [p.actual, p.predicted]), 100)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 10, right: 16, bottom: 6, left: -6 }}>
        <CartesianGrid {...GRID} />
        <XAxis type="number" dataKey="actual" name="Actual" {...AX} domain={[0, max]}
          tickLine={false} axisLine={false} label={{ value: 'Actual AQI', position: 'insideBottom', offset: -2, fill: '#71717a', fontSize: 11 }} />
        <YAxis type="number" dataKey="predicted" name="Predicted" {...AX} domain={[0, max]}
          tickLine={false} axisLine={false} width={44} />
        <Tooltip {...tip} cursor={{ strokeDasharray: '3 3' }} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: max, y: max }]} stroke="#8b5cf6" strokeDasharray="5 5" />
        <Scatter data={points} fill="#a78bfa" fillOpacity={0.5} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
