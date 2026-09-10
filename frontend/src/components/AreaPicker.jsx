import { useSelection } from './SelectionContext'
import './area-picker.css'

export default function AreaPicker({ compact = false }) {
  const { states, state, setState, areas, area, setArea, areaLevel } = useSelection()
  return (
    <div className={`area-picker ${compact ? 'compact' : ''}`}>
      <label className="ap-field">
        <span>State</span>
        <select value={state} onChange={(e) => setState(e.target.value)}>
          {states.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <label className="ap-field">
        <span>{areaLevel === 'district' ? 'District' : 'City / Station area'}</span>
        <select value={area} onChange={(e) => setArea(e.target.value)}>
          {areas.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
      </label>
    </div>
  )
}
