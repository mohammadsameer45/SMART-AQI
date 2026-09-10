// CPCB AQI categories — mirrors backend/config/aqi_categories.py.
export const AQI_BANDS = [
  { label: 'Good', lo: 0, hi: 50, color: 'var(--aqi-good)', hex: '#2e9e4f' },
  { label: 'Satisfactory', lo: 51, hi: 100, color: 'var(--aqi-satisfactory)', hex: '#7bb93f' },
  { label: 'Moderate', lo: 101, hi: 200, color: 'var(--aqi-moderate)', hex: '#f0c030' },
  { label: 'Poor', lo: 201, hi: 300, color: 'var(--aqi-poor)', hex: '#f08b24' },
  { label: 'Very Poor', lo: 301, hi: 400, color: 'var(--aqi-verypoor)', hex: '#e24b4b' },
  { label: 'Severe', lo: 401, hi: 500, color: 'var(--aqi-severe)', hex: '#8b2e8b' },
]

export function bandFor(aqi) {
  if (aqi == null || Number.isNaN(aqi)) return null
  return AQI_BANDS.find((b) => aqi <= b.hi) ?? AQI_BANDS[AQI_BANDS.length - 1]
}

export const aqiColor = (aqi) => bandFor(aqi)?.hex ?? '#71717a'
export const aqiLabel = (aqi) => bandFor(aqi)?.label ?? '—'
export const aqiDisplay = (aqi) => (aqi == null ? '—' : Math.min(Math.round(aqi), 500) + (aqi > 500 ? '+' : ''))

export const fmtDate = (s) =>
  s ? new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''
export const fmtDateLong = (s) =>
  s ? new Date(s).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : ''
