import { useEffect, useState } from 'react'
import { AQI_BANDS, aqiColor, aqiLabel, aqiDisplay } from '../utils/aqi'
import './aqi-gauge.css'

/** Animated 270° arc gauge. Not a flat progress bar. */
export default function AQIGauge({ value, size = 260, max = 500 }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const target = value ?? 0
    let raf, start
    const dur = 900
    const from = shown
    const step = (t) => {
      if (!start) start = t
      const k = Math.min((t - start) / dur, 1)
      const e = 1 - Math.pow(1 - k, 3)
      setShown(from + (target - from) * e)
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  const R = size / 2 - 18
  const cx = size / 2
  const cy = size / 2
  const START = 135 // deg
  const SWEEP = 270
  const frac = Math.min(Math.max(shown / max, 0), 1)

  const polar = (deg) => {
    const r = (deg * Math.PI) / 180
    return [cx + R * Math.cos(r), cy + R * Math.sin(r)]
  }
  const arc = (a0, a1) => {
    const [x0, y0] = polar(a0)
    const [x1, y1] = polar(a1)
    const large = a1 - a0 > 180 ? 1 : 0
    return `M ${x0} ${y0} A ${R} ${R} 0 ${large} 1 ${x1} ${y1}`
  }

  return (
    <div className="gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <path d={arc(START, START + SWEEP)} className="gauge-track" />
        {/* coloured band segments */}
        {AQI_BANDS.map((b) => {
          const a0 = START + (b.lo / max) * SWEEP
          const a1 = START + (Math.min(b.hi, max) / max) * SWEEP
          return <path key={b.label} d={arc(a0, a1)} stroke={b.hex} className="gauge-band" />
        })}
        {/* active progress */}
        <path
          d={arc(START, START + frac * SWEEP)}
          stroke={aqiColor(shown)}
          className="gauge-progress"
        />
        {(() => {
          const [nx, ny] = polar(START + frac * SWEEP)
          return <circle cx={nx} cy={ny} r={7} fill="#fff" className="gauge-knob" />
        })()}
      </svg>
      <div className="gauge-center">
        <div className="gauge-num" style={{ color: aqiColor(shown) }}>{aqiDisplay(shown)}</div>
        <div className="gauge-cat">{value == null ? 'No data' : aqiLabel(shown)}</div>
        <div className="gauge-sub tiny muted">Air Quality Index</div>
      </div>
    </div>
  )
}
