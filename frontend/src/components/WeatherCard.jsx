import { GlassCard, SectionTitle } from './ui/Bits'
import { fmtDate } from '../utils/aqi'
import './weather-card.css'

const ICON = {
  Clear: '☀', 'Mainly clear': '🌤', 'Partly cloudy': '⛅', Overcast: '☁',
  Fog: '🌫', 'Rime fog': '🌫', 'Light drizzle': '🌦', Drizzle: '🌦',
  'Heavy drizzle': '🌧', 'Light rain': '🌦', Rain: '🌧', 'Heavy rain': '🌧',
  'Rain showers': '🌦', 'Violent rain showers': '⛈', 'Light snow': '🌨',
  Snow: '🌨', 'Heavy snow': '❄', Thunderstorm: '⛈',
  'Thunderstorm with hail': '⛈', 'Freezing rain': '🌧',
}

export default function WeatherCard({ weather }) {
  if (!weather) return null
  if (!weather.available) {
    return (
      <GlassCard className="card">
        <SectionTitle eyebrow="Weather" title="Open-Meteo" />
        <p className="muted tiny">{weather.reason}</p>
      </GlassCard>
    )
  }
  const c = weather.current
  const u = weather.units
  return (
    <GlassCard className="card weather-card">
      <SectionTitle eyebrow="Weather · Open-Meteo" title={c.condition} right={
        <span className="wx-big">{ICON[c.condition] || '🌡'}</span>
      } />
      <div className="wx-now">
        <div className="wx-temp">{Math.round(c.temperature)}<span>{u.temperature}</span></div>
        <div className="wx-metrics">
          <div><b>{c.humidity}{u.humidity}</b><span>Humidity</span></div>
          <div><b>{c.wind_speed} {u.wind_speed}</b><span>Wind</span></div>
          <div><b>{Math.round(c.pressure)} {u.pressure}</b><span>Pressure</span></div>
          <div><b>{c.rainfall} {u.rainfall}</b><span>Rain</span></div>
        </div>
      </div>
      <div className="wx-week">
        {weather.daily.slice(1, 7).map((d) => (
          <div key={d.date} className="wx-day">
            <span className="wx-dow">{fmtDate(d.date)}</span>
            <span className="wx-ic">{ICON[d.condition] || '·'}</span>
            <span className="wx-range">{Math.round(d.t_max)}° / {Math.round(d.t_min)}°</span>
          </div>
        ))}
      </div>
      <div className="card-note">
        Reference point: {weather.location.reference_station} · {weather.source}
      </div>
    </GlassCard>
  )
}
