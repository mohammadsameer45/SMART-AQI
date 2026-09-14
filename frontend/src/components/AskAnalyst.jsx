import { useRef, useState, useEffect } from 'react'
import { useSelection } from './SelectionContext'
import { aqi as aqiApi } from '../api/endpoints'
import './ask-analyst.css'

const SUGGESTIONS = [
  'Is pollution improving?',
  'Why is AQI high?',
  'Is it safe to go for a walk?',
  'Which pollutant is causing the problem?',
]

export default function AskAnalyst() {
  const { state, area } = useSelection()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState([])
  const endRef = useRef(null)

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log, open])

  const ask = async (q) => {
    const question = (q ?? input).trim()
    if (!question || !state || !area || busy) return
    setInput('')
    setLog((l) => [...l, { role: 'q', text: question }])
    setBusy(true)
    try {
      const d = await aqiApi.analyst(state, area, question)
      setLog((l) => [...l, { role: 'a', text: d.available ? d.answer : (d.reason || "Couldn't answer that.") }])
    } catch {
      setLog((l) => [...l, { role: 'a', text: 'Something went wrong reaching the analyst.' }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button className="analyst-fab" onClick={() => setOpen((o) => !o)} aria-label="Ask AQI Analyst">
        {open ? '✕' : '💬'}
      </button>
      {open && (
        <div className="analyst-panel glass">
          <div className="analyst-head">
            <div>
              <div className="eyebrow">AQI Analyst</div>
              <div className="tiny muted">{area && state ? `${area}, ${state}` : 'Select an area first'}</div>
            </div>
          </div>
          <div className="analyst-log">
            {log.length === 0 && (
              <p className="tiny muted">Ask about the currently selected area's AQI, pollutants, trend, forecast, or safety.</p>
            )}
            {log.map((m, i) => (
              <div key={i} className={`analyst-msg ${m.role}`}>{m.text}</div>
            ))}
            {busy && <div className="analyst-msg a"><span className="spin" /></div>}
            <div ref={endRef} />
          </div>
          <div className="analyst-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="src-chip" onClick={() => ask(s)} disabled={busy || !state || !area}>{s}</button>
            ))}
          </div>
          <form className="analyst-input" onSubmit={(e) => { e.preventDefault(); ask() }}>
            <input value={input} onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…" disabled={!state || !area} />
            <button type="submit" className="btn btn-ghost" disabled={busy || !input.trim() || !state || !area}>Send</button>
          </form>
        </div>
      )}
    </>
  )
}
