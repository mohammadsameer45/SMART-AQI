import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import * as THREE from 'three'
import { aqiColor, aqiDisplay } from '../utils/aqi'

// India bbox roughly 68-98 E, 6-37 N — project to a flat XZ plane.
const C_LON = 82.5
const C_LAT = 23
const K = 0.34
const project = (lon, lat) => [(lon - C_LON) * K, -(lat - C_LAT) * K]

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

function Region({ feature, onSelect, dim }) {
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
      const y = hover ? 0.25 : 0
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
        emissive={color}
        emissiveIntensity={hover ? 0.55 : p.has_data ? 0.18 : 0.03}
        roughness={0.55}
        metalness={0.1}
        transparent
        opacity={dim && !p.has_data ? 0.35 : 1}
      />
      {hover && (
        <Html center distanceFactor={10} style={{ pointerEvents: 'none' }}>
          <div className="map3d-tip">
            <b>{p.name}</b>
            {p.has_data
              ? <> · AQI {aqiDisplay(p.aqi)} · {p.aqi_bucket}
                  {p.n_stations ? ` · ${p.n_stations} stn` : ''}</>
              : ' · no data'}
          </div>
        </Html>
      )}
    </mesh>
  )
}

function Spin({ children, enabled }) {
  const g = useRef()
  useFrame((_, dt) => { if (g.current && enabled) g.current.rotation.y += dt * 0.04 })
  return <group ref={g}>{children}</group>
}

export default function IndiaMap3D({ data, onSelect, autoRotate = true }) {
  const feats = data?.features ?? []
  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[6, 12, 8]} intensity={1.4} castShadow />
      <directionalLight position={[-8, 6, -6]} intensity={0.5} color="#a78bfa" />
      <Spin enabled={autoRotate}>
        <group position={[0, 0, 0]}>
          {feats.map((f, i) => (
            <Region key={f.properties.name + i} feature={f} onSelect={onSelect}
              dim={data?.level === 'state'} />
          ))}
        </group>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow>
          <planeGeometry args={[26, 26]} />
          <meshStandardMaterial color="#070709" roughness={1} />
        </mesh>
      </Spin>
      <OrbitControls
        enablePan={false} minDistance={7} maxDistance={20}
        minPolarAngle={0.15} maxPolarAngle={Math.PI / 2.15}
      />
    </>
  )
}
