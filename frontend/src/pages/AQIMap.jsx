import { useState } from 'react'
import { useSelection } from '../components/SelectionContext'
import { useApi } from '../hooks/useApi'
import api from '../api/client'
import SceneCanvas from '../three/SceneCanvas'
import IndiaMap3D from '../three/IndiaMap3D'
import { GlassCard, Loader, ErrorState, SectionTitle, AQIChip } from '../components/ui/Bits'
import { AQI_BANDS, bandFor } from '../utils/aqi'
import './dash-pages.css'
import './aqi-map.css'

export default function AQIMap() {
  const { state, setState, setArea } = useSelection()
  const [drill, setDrill] = useState(null)   // null = India, else a state name
  const [rotate, setRotate] = useState(true)

  const map = useApi(
    () => api.get(drill ? `/map/state/${encodeURIComponent(drill)}` : '/map/india'),
    [drill],
  )

  const onSelect = (props) => {
    if (!drill) {
      if (props.dataset_state) { setState(props.dataset_state); setDrill(props.dataset_state) }
    } else if (props.has_data) {
      setArea(props.name)          // district -> set the global selection
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>3D AQI Map</h1>
        <p>{drill ? `${drill} — districts with data` : 'India — states, extruded by current AQI'}</p>
      </div>

      <GlassCard className="card">
        <SectionTitle
          eyebrow="Interactive"
          title={drill || 'India'}
          right={
            <div className="map-actions">
              {drill && (
                <button className="btn btn-ghost" onClick={() => setDrill(null)}>← India</button>
              )}
              <button className="btn btn-ghost" onClick={() => setRotate((r) => !r)}>
                {rotate ? 'Pause spin' : 'Auto-rotate'}
              </button>
            </div>
          }
        />

        <div className="canvas-box tall map3d-box">
          {map.loading ? <Loader label="Loading map…" />
            : map.error ? <ErrorState error={map.error} onRetry={map.refetch} />
            : (
              <SceneCanvas camera={{ position: [0, 11, 9], fov: 42 }}
                style={{ width: '100%', height: '100%' }} fallback={<div />}>
                <IndiaMap3D data={map.data} onSelect={onSelect} autoRotate={rotate} />
              </SceneCanvas>
            )}
        </div>

        <div className="map-legend">
          {AQI_BANDS.map((b) => (
            <span key={b.label} className="ml-item">
              <span className="ml-sw" style={{ background: b.hex }} /> {b.label}
            </span>
          ))}
          <span className="ml-item"><span className="ml-sw" style={{ background: '#181820' }} /> No data</span>
        </div>
        <div className="card-note">
          Bar height &amp; colour = current AQI. Click a {drill ? 'district to select it' : 'state to drill in'} ·
          drag to orbit · scroll to zoom.
        </div>
      </GlassCard>

      {map.data?.level === 'state' && (
        <GlassCard className="card" style={{ marginTop: 18 }}>
          <SectionTitle title="Districts" />
          <div className="pill-row">
            {map.data.features
              .filter((f) => f.properties.aqi != null)
              .sort((a, b) => b.properties.aqi - a.properties.aqi)
              .map((f) => {
                const p = f.properties
                return <AQIChip key={p.name} label={`${p.name} · ${p.aqi}`} color={bandFor(p.aqi)?.hex} />
              })}
          </div>
        </GlassCard>
      )}
    </div>
  )
}
