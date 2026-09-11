import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { geo, leaderboard as leaderboardApi } from '../api/endpoints'
import { GlassCard, Loader, ErrorState, SectionTitle, AQIChip } from '../components/ui/Bits'
import { bandFor, aqiDisplay } from '../utils/aqi'
import './dash-pages.css'
import './leaderboard.css'

const MAX_SLOTS = 4
const MIN_SLOTS = 2

function useAreasFor(state) {
  const [areas, setAreas] = useState([])
  useEffect(() => {
    if (!state) { setAreas([]); return }
    let alive = true
    geo.areas(state).then((r) => { if (alive) setAreas(r.items) }).catch(() => alive && setAreas([]))
    return () => { alive = false }
  }, [state])
  return areas
}

function CompareRow({ states, value, onChange, onRemove, removable }) {
  const areas = useAreasFor(value.state)
  return (
    <div className="cmp-row">
      <select value={value.state}
        onChange={(e) => onChange({ state: e.target.value, area: '' })}>
        {states.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <select value={value.area} onChange={(e) => onChange({ ...value, area: e.target.value })}>
        <option value="">Select area…</option>
        {areas.map((a) => <option key={a} value={a}>{a}</option>)}
      </select>
      {removable && (
        <button className="btn btn-ghost cmp-remove" onClick={onRemove} aria-label="Remove">✕</button>
      )}
    </div>
  )
}

function RankList({ title, eyebrow, rows, accent }) {
  return (
    <GlassCard className="card">
      <SectionTitle eyebrow={eyebrow} title={title} />
      <ol className="rank-list">
        {rows.map((r, i) => {
          const band = bandFor(r.aqi)
          return (
            <li key={`${r.state}-${r.district}`} className="rank-row">
              <span className="rank-num" style={{ color: accent }}>{i + 1}</span>
              <span className="rank-name">
                {r.district}<span className="tiny muted"> · {r.state}</span>
              </span>
              <AQIChip label={aqiDisplay(r.aqi)} color={band?.hex} />
            </li>
          )
        })}
      </ol>
    </GlassCard>
  )
}

const COMPARE_FIELDS = [
  { key: 'AQI', label: 'AQI', fmt: (v) => (v == null ? '—' : Math.round(v)) },
  { key: '__category', label: 'Category' },
  { key: '__source', label: 'Source' },
  { key: 'PM25', label: 'PM2.5 (µg/m³)', fmt: fmtNum },
  { key: 'PM10', label: 'PM10 (µg/m³)', fmt: fmtNum },
  { key: 'NO2', label: 'NO₂ (µg/m³)', fmt: fmtNum },
  { key: 'O3', label: 'O₃ (µg/m³)', fmt: fmtNum },
]
function fmtNum(v) { return v == null ? '—' : Math.round(v) }

export default function Leaderboard() {
  const { data: states } = useApi(() => geo.states(), [])
  const lb = useApi(() => leaderboardApi.national(), [])
  const [slots, setSlots] = useState([{ state: '', area: '' }, { state: '', area: '' }])
  const [result, setResult] = useState(null)
  const [comparing, setComparing] = useState(false)
  const [cmpError, setCmpError] = useState('')

  useEffect(() => {
    if (states?.length) {
      setSlots((s) => s.map((slot) => (slot.state ? slot : { ...slot, state: states[0] })))
    }
  }, [states])

  const updateSlot = (i, val) => setSlots((s) => s.map((x, idx) => (idx === i ? val : x)))
  const addSlot = () => setSlots((s) => (s.length < MAX_SLOTS ? [...s, { state: states?.[0] || '', area: '' }] : s))
  const removeSlot = (i) => setSlots((s) => (s.length > MIN_SLOTS ? s.filter((_, idx) => idx !== i) : s))

  const addToCompare = (state, district) => {
    setSlots((s) => {
      const emptyIdx = s.findIndex((x) => !x.area)
      const next = [...s]
      if (emptyIdx >= 0) next[emptyIdx] = { state, area: district }
      else next[next.length - 1] = { state, area: district }
      return next
    })
  }

  const runCompare = async () => {
    const ready = slots.filter((s) => s.state && s.area)
    if (ready.length < MIN_SLOTS) { setCmpError(`Pick at least ${MIN_SLOTS} areas.`); return }
    setCmpError('')
    setComparing(true)
    try {
      const pairs = ready.map((s) => `${s.state}:${s.area}`)
      const r = await leaderboardApi.compare(pairs)
      setResult(r.areas)
    } catch (e) {
      setCmpError(e.message || 'Comparison failed.')
    } finally {
      setComparing(false)
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Leaderboard &amp; Compare</h1>
        <p>Live nationwide district ranking, and a side-by-side comparison of any 2–4 areas.</p>
      </div>

      {lb.loading ? <Loader label="Loading leaderboard…" />
        : lb.error ? <ErrorState error={lb.error} onRetry={lb.refetch} />
        : (
          <>
            <div className="grid g-2" style={{ marginBottom: 18 }}>
              <RankList title="Cleanest districts" eyebrow={`${lb.data.n_districts} districts tracked`}
                rows={lb.data.best} accent="var(--aqi-good)" />
              <RankList title="Most polluted districts" eyebrow="Right now"
                rows={lb.data.worst} accent="var(--aqi-verypoor)" />
            </div>
            <p className="tiny muted" style={{ marginTop: -8, marginBottom: 18 }}>
              Click ● on the compare tool below, or add these directly —
              generated {new Date(lb.data.generated_at).toLocaleString()}.
            </p>
          </>
        )}

      <GlassCard className="card">
        <SectionTitle eyebrow="Side by side" title="Compare areas" />
        {states?.length ? (
          <>
            <div className="cmp-rows">
              {slots.map((slot, i) => (
                <CompareRow key={i} states={states} value={slot}
                  onChange={(v) => updateSlot(i, v)}
                  onRemove={() => removeSlot(i)} removable={slots.length > MIN_SLOTS} />
              ))}
            </div>
            <div className="cmp-actions">
              <button className="btn btn-ghost" onClick={addSlot} disabled={slots.length >= MAX_SLOTS}>
                + Add area
              </button>
              <button className="btn btn-primary" onClick={runCompare} disabled={comparing}>
                {comparing ? 'Comparing…' : 'Compare'}
              </button>
            </div>
            {cmpError && <p className="tiny" style={{ color: 'var(--aqi-verypoor)', marginTop: 8 }}>{cmpError}</p>}

            {result && (
              <div className="table-scroll" style={{ marginTop: 18 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      {result.map((a) => (
                        <th key={`${a.state}-${a.area}`}>{a.area}<div className="tiny muted">{a.state}</div></th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {COMPARE_FIELDS.map((f) => (
                      <tr key={f.key}>
                        <td>{f.label}</td>
                        {result.map((a) => {
                          const c = a.current
                          let val
                          if (!c.available) val = '—'
                          else if (f.key === '__category') val = c.AQI_bucket
                          else if (f.key === '__source') val = c.is_live ? 'LIVE' : 'HISTORICAL'
                          else if (f.key === 'AQI') val = f.fmt(c.AQI)
                          else val = f.fmt(c.pollutants?.[f.key])
                          const band = f.key === 'AQI' && c.available ? bandFor(c.AQI) : null
                          return (
                            <td key={`${a.state}-${a.area}-${f.key}`}
                              style={band ? { color: band.hex, fontWeight: 700 } : undefined}>
                              {val}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : <Loader />}
      </GlassCard>

      {!lb.loading && !lb.error && (
        <GlassCard className="card" style={{ marginTop: 18 }}>
          <SectionTitle title="Quick add from the leaderboard" />
          <div className="pill-row">
            {[...lb.data.best, ...lb.data.worst].map((r) => {
              const band = bandFor(r.aqi)
              return (
                <AQIChip key={`${r.state}-${r.district}`} label={`${r.district} · ${r.aqi}`}
                  color={band?.hex} onClick={() => addToCompare(r.state, r.district)} />
              )
            })}
          </div>
        </GlassCard>
      )}
    </div>
  )
}
