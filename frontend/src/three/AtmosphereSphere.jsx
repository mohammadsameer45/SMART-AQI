import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

/**
 * A literal AQI atmosphere: a hazy sky of soft cloud puffs drifting right to
 * left, plus a field of fine drifting particulate. The mix of white "clean
 * air" cloud to dark "pollution" cloud - not a hue ramp - is what encodes
 * `aqi`, so a bad reading reads as a genuinely smoggier sky rather than an
 * arbitrary colour swap.
 */

let puffTexture = null
function getPuffTexture() {
  if (puffTexture) return puffTexture
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.45, 'rgba(255,255,255,0.5)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, size, size)
  puffTexture = new THREE.CanvasTexture(canvas)
  return puffTexture
}

/** One drifting layer of soft cloud puffs, wrapping right-to-left. */
function CloudLayer({ count, color, size, opacity, speed, spreadY, depth, blending }) {
  const ref = useRef()
  const texture = useMemo(() => getPuffTexture(), [])
  const baseX = 9
  const { positions, seeds } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const seeds = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() * 2 - 1) * baseX
      positions[i * 3 + 1] = (Math.random() * 2 - 1) * spreadY
      positions[i * 3 + 2] = depth - Math.random() * 1.4
      seeds[i] = Math.random() * Math.PI * 2
    }
    return { positions, seeds }
  }, [count, spreadY, depth])

  useFrame((state, delta) => {
    const pts = ref.current
    if (!pts) return
    const arr = pts.geometry.attributes.position.array
    const t = state.clock.elapsedTime
    for (let i = 0; i < count; i++) {
      arr[i * 3] -= speed * delta                                     // right -> left drift
      if (arr[i * 3] < -baseX) arr[i * 3] = baseX                     // loop back around
      arr[i * 3 + 1] += Math.sin(t * 0.18 + seeds[i]) * 0.0012        // gentle vertical bob
    }
    pts.geometry.attributes.position.needsUpdate = true
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial map={texture} size={size} color={color} transparent opacity={opacity}
        depthWrite={false} blending={blending} sizeAttenuation />
    </points>
  )
}

/** Fine, fast drifting particulate - the "dust in the air" layer. */
function DustMotes({ count, color, agitation, speed }) {
  const ref = useRef()
  const baseX = 8
  const { positions, seeds } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const seeds = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const r = 1.6 + Math.random() * 2.2
      const theta = Math.random() * Math.PI * 2
      const y = (Math.random() * 2 - 1) * 1.8
      positions[i * 3] = Math.cos(theta) * r
      positions[i * 3 + 1] = y
      positions[i * 3 + 2] = Math.sin(theta) * r - 1
      seeds[i] = Math.random() * 10
    }
    return { positions, seeds }
  }, [count])

  useFrame((state, delta) => {
    const pts = ref.current
    if (!pts) return
    const arr = pts.geometry.attributes.position.array
    const t = state.clock.elapsedTime
    for (let i = 0; i < count; i++) {
      const s = seeds[i]
      arr[i * 3] -= speed * delta
      if (arr[i * 3] < -baseX) arr[i * 3] = baseX
      arr[i * 3 + 1] += Math.sin(t * (0.5 + agitation) + s) * 0.01 * (0.4 + agitation)
    }
    pts.geometry.attributes.position.needsUpdate = true
    const { x, y } = state.pointer
    pts.rotation.y += x * delta * 0.05
    pts.rotation.x += -y * delta * 0.03
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.03} color={color} transparent opacity={0.75} depthWrite={false}
        blending={THREE.AdditiveBlending} sizeAttenuation />
    </points>
  )
}

const CLEAN_WHITE = new THREE.Color('#f4f6ff')
const POLLUTION_HAZE = new THREE.Color('#8b8b93')
const POLLUTION_SMOG = new THREE.Color('#241f1c')
const DUST_CLEAN = new THREE.Color('#a9c6ff')
const DUST_DIRTY = new THREE.Color('#9c8264')

export default function AtmosphereScene({ aqi = 120, focus = 0 }) {
  const norm = Math.min(Math.max(aqi / 400, 0), 1)              // 0 clean -> 1 severe

  const pollutionColor = useMemo(
    () => POLLUTION_HAZE.clone().lerp(POLLUTION_SMOG, norm), [norm])
  const dustColor = useMemo(
    () => DUST_CLEAN.clone().lerp(DUST_DIRTY, norm), [norm])

  const cleanCount = Math.round(26 - norm * 16)
  const pollutionCount = Math.round(8 + norm * 26)
  const duskGlow = 0.16 + focus * 0.1

  return (
    <group>
      <ambientLight intensity={0.5} />
      <pointLight position={[4, 3, 5]} intensity={28} color="#a78bfa" />
      <mesh position={[0, 0, -4]}>
        <sphereGeometry args={[2.1, 24, 24]} />
        <meshBasicMaterial color="#7c3aed" transparent opacity={duskGlow} />
      </mesh>

      {/* white "clean air" clouds - higher up, brighter, thin out as AQI worsens */}
      <CloudLayer count={cleanCount} color={CLEAN_WHITE} size={2.4}
        opacity={0.22 + (1 - norm) * 0.2} speed={0.32 + focus * 0.1}
        spreadY={2.1} depth={-2.4} blending={THREE.AdditiveBlending} />

      {/* dark pollution clouds - lower, denser and thicker as AQI worsens */}
      <CloudLayer count={pollutionCount} color={pollutionColor} size={2.8}
        opacity={0.24 + norm * 0.42} speed={0.2 + focus * 0.06}
        spreadY={1.5} depth={-1.3} blending={THREE.NormalBlending} />

      <DustMotes count={520} color={dustColor} agitation={norm + focus * 0.4}
        speed={0.5 + focus * 0.2} />
    </group>
  )
}
