import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import * as THREE from 'three'
import { aqiColor, aqiDisplay } from '../utils/aqi'

// India bbox roughly 68-98 E, 6-37 N — project to a flat XZ plane.
// Each region's shape is extruded flat then rotateX(-PI/2) maps local Y -> world -Z, so a
// local Y that INCREASES with latitude puts higher latitude (north) at
// world -Z (far from the default camera) and lower latitude (south) at
// world +Z (near the camera) — i.e. north renders at the top of the view,
// south at the bottom, matching real-world orientation.
const C_LON = 82.5
const C_LAT = 23
const K = 0.34
const project = (lon, lat) => [(lon - C_LON) * K, (lat - C_LAT) * K]

function polygonsOf(geom) {
  if (!geom) return []
  return geom.type === 'MultiPolygon' ? geom.coordinates : [geom.coordinates]
}

function shapeFromRings(rings) {
  const [outer, ...holes] = rings
  const s = new THREE.Shape()
  outer.forEach(([lon, lat], i) => {
    const [x, y] = project(lon, lat)
    i ? s.lineTo(x, y) : s.moveTo(x, y)
  })
  holes.forEach((h) => {
    const path = new THREE.Path()
    h.forEach(([lon, lat], i) => {
      const [x, y] = project(lon, lat)
      i ? path.lineTo(x, y) : path.moveTo(x, y)
    })
    s.holes.push(path)
  })
  return s
}

// Lightweight centroid (mean of the largest ring's projected vertices) — good
// enough to point a camera at, not a true area centroid. Returns WORLD [x, z]
// (not the raw pre-rotation projected [x, y]) — Region's geometry applies
// rotateX(-PI/2), which maps local y -> world -z, so this must negate the
// averaged y the same way or the marker/camera focus lands mirrored
// north<->south from the region it's supposed to mark.
function centroidOf(feature) {
  const polys = polygonsOf(feature?.geometry)
  if (!polys.length) return null
  let ring = polys[0][0]
  for (const poly of polys) if (poly[0].length > ring.length) ring = poly[0]
  let sx = 0, sy = 0
  ring.forEach(([lon, lat]) => { const [x, y] = project(lon, lat); sx += x; sy += y })
  return [sx / ring.length, -(sy / ring.length)]
}

function regionMatches(feature, level, selected) {
  if (!selected) return false
  const p = feature.properties
  return level === 'state' ? p.dataset_state === selected : p.name === selected
}

function Region({ feature, onSelect, dim, selected }) {
  const p = feature.properties
  const ref = useRef()
  const [hover, setHover] = useState(false)

  const height = p.has_data
    ? 0.12 + Math.min(p.aqi ?? 0, 400) / 400 * 2.6
    : 0.06
  const color = p.has_data ? aqiColor(p.aqi) : '#181820'

  const geometry = useMemo(() => {
    const shapes = polygonsOf(feature.geometry).map(shapeFromRings)
    const g = new THREE.ExtrudeGeometry(shapes, {
      depth: height, bevelEnabled: false, steps: 1,
    })
    g.rotateX(-Math.PI / 2)          // lay flat, extrude -> +Y
    g.computeVertexNormals()
    return g
  }, [feature, height])

  useEffect(() => () => geometry.dispose(), [geometry])

  useFrame(() => {
    if (ref.current) {
      const y = hover || selected ? 0.25 : 0
      ref.current.position.y += (y - ref.current.position.y) * 0.2
    }
  })

  return (
    <mesh
      ref={ref}
      geometry={geometry}
      onPointerOver={(e) => { e.stopPropagation(); setHover(true) }}
      onPointerOut={() => setHover(false)}
      onClick={(e) => { e.stopPropagation(); onSelect?.(p) }}
      castShadow
      receiveShadow
    >
      <meshStandardMaterial
        color={color}
        emissive={selected ? '#ffffff' : color}
        emissiveIntensity={hover ? 0.55 : selected ? 0.42 : p.has_data ? 0.18 : 0.03}
        roughness={0.55}
        metalness={0.1}
        transparent
        opacity={dim && !p.has_data ? 0.35 : 1}
      />
      {hover && (
        <Html center distanceFactor={10} style={{ pointerEvents: 'none' }}>
          <div className="map3d-tip">
            <b>{p.name}</b>{p.state ? `, ${p.state}` : ''}
            {p.has_data
              ? <>
                  <br />AQI {aqiDisplay(p.aqi)} · {p.aqi_bucket}
                  {p.n_stations ? ` · ${p.n_stations} stn` : ''}
                  {(p.pm25 != null || p.pm10 != null) && (
                    <><br />{p.pm25 != null ? `PM2.5 ${p.pm25}` : ''}
                      {p.pm25 != null && p.pm10 != null ? ' · ' : ''}
                      {p.pm10 != null ? `PM10 ${p.pm10}` : ''}</>
                  )}
                  {p.last_updated && <><br /><span className="muted">Updated {new Date(p.last_updated).toLocaleString()}</span></>}
                </>
              : ' · no data'}
          </div>
        </Html>
      )}
    </mesh>
  )
}

function SelectedMarker({ position }) {
  const ring = useRef()
  const t = useRef(0)
  useFrame((_, dt) => {
    t.current += dt
    if (ring.current) {
      const s = 1 + Math.sin(t.current * 2.2) * 0.14
      ring.current.scale.set(s, 1, s)
      ring.current.material.opacity = 0.55 + Math.sin(t.current * 2.2) * 0.25
    }
  })
  if (!position) return null
  const [x, z] = position
  return (
    <group position={[x, 0, z]}>
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.06, 0]}>
        <ringGeometry args={[0.3, 0.44, 48]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.7} depthWrite={false} />
      </mesh>
      <mesh position={[0, 1.6, 0]}>
        <cylinderGeometry args={[0.018, 0.018, 3.2, 8]} />
        <meshBasicMaterial color="#a78bfa" transparent opacity={0.5} depthWrite={false} />
      </mesh>
      <pointLight position={[0, 1, 0]} color="#a78bfa" intensity={1.3} distance={4} />
    </group>
  )
}

// Pans the OrbitControls target (and camera by the same delta, preserving
// the current orbit distance/angle) toward the selected region's centroid.
function CameraRig({ focus, controlsRef }) {
  const { camera } = useThree()
  useFrame(() => {
    const controls = controlsRef.current
    if (!controls) return
    const desired = focus ? new THREE.Vector3(focus[0], 0, focus[1]) : new THREE.Vector3(0, 0, 0)
    const delta = desired.clone().sub(controls.target)
    if (delta.lengthSq() < 0.0005) return
    delta.multiplyScalar(0.07)
    controls.target.add(delta)
    camera.position.add(delta)
    controls.update()
  })
  return null
}

export default function IndiaMap3D({ data, onSelect, autoRotate = true, selected }) {
  const feats = data?.features ?? []
  const level = data?.level
  const groupRef = useRef()
  const controlsRef = useRef()
  const spinning = autoRotate && !selected

  // While a region is selected the map settles to its neutral (un-rotated)
  // angle so projected coordinates line up with the camera focus & marker.
  useFrame((_, dt) => {
    const g = groupRef.current
    if (!g) return
    if (spinning) {
      g.rotation.y += dt * 0.04
    } else {
      const twoPi = Math.PI * 2
      const nearest = Math.round(g.rotation.y / twoPi) * twoPi
      g.rotation.y += (nearest - g.rotation.y) * Math.min(1, dt * 2.5)
    }
  })

  const selectedFeature = useMemo(
    () => feats.find((f) => regionMatches(f, level, selected)),
    [feats, level, selected],
  )
  const focus = useMemo(() => (selectedFeature ? centroidOf(selectedFeature) : null), [selectedFeature])

  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[6, 12, 8]} intensity={1.4} castShadow />
      <directionalLight position={[-8, 6, -6]} intensity={0.5} color="#a78bfa" />
      <group ref={groupRef} position={[0, 0, 0]}>
        {feats.map((f, i) => (
          <Region key={f.properties.name + i} feature={f} onSelect={onSelect}
            dim={data?.level === 'state'} selected={regionMatches(f, level, selected)} />
        ))}
        <SelectedMarker position={focus} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow>
          <planeGeometry args={[26, 26]} />
          <meshStandardMaterial color="#070709" roughness={1} />
        </mesh>
      </group>
      <CameraRig focus={focus} controlsRef={controlsRef} />
      <OrbitControls
        ref={controlsRef}
        enablePan={false} minDistance={7} maxDistance={20}
        minPolarAngle={0.15} maxPolarAngle={Math.PI / 2.15}
      />
    </>
  )
}
