import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

/**
 * A glowing shell of pollutant particles around a soft core. Particle count,
 * colour and agitation scale with `aqi`. Reacts subtly to the pointer.
 * Genuine 3D — instanced points on a sphere, animated per frame.
 */
function Particles({ count, color, agitation }) {
  const ref = useRef()
  const { positions, seeds } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const seeds = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const r = 2 + Math.random() * 1.15
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = r * Math.cos(phi)
      seeds[i] = Math.random() * 10
    }
    return { positions, seeds }
  }, [count])

  useFrame((state, delta) => {
    const pts = ref.current
    if (!pts) return
    pts.rotation.y += delta * 0.06
    pts.rotation.x += delta * 0.015
    const arr = pts.geometry.attributes.position.array
    const t = state.clock.elapsedTime
    for (let i = 0; i < count; i++) {
      const s = seeds[i]
      const wobble = Math.sin(t * (0.4 + agitation) + s) * 0.015 * (0.4 + agitation)
      arr[i * 3 + 1] += wobble
    }
    pts.geometry.attributes.position.needsUpdate = true
    // pointer parallax
    const { x, y } = state.pointer
    pts.rotation.y += x * delta * 0.15
    pts.rotation.x += -y * delta * 0.1
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.035}
        color={color}
        transparent
        opacity={0.85}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        sizeAttenuation
      />
    </points>
  )
}

export default function AtmosphereSphere({ aqi = 120, focus = 0 }) {
  const norm = Math.min(Math.max(aqi / 400, 0), 1)
  const count = Math.round(1400 + norm * 2600)
  const color = useMemo(() => {
    // green -> amber -> red -> violet, roughly the AQI ramp
    const c = new THREE.Color()
    c.setHSL(0.34 - norm * 0.42 + (norm > 0.85 ? -0.15 : 0), 0.7, 0.55)
    return c
  }, [norm])
  const coreRef = useRef()
  useFrame((state) => {
    if (coreRef.current) {
      const p = 1 + Math.sin(state.clock.elapsedTime * 1.2) * 0.03 + focus * 0.08
      coreRef.current.scale.setScalar(p)
    }
  })

  return (
    <group>
      <ambientLight intensity={0.4} />
      <pointLight position={[4, 3, 5]} intensity={40} color="#a78bfa" />
      <mesh ref={coreRef}>
        <icosahedronGeometry args={[1.35, 4]} />
        <meshStandardMaterial
          color="#1a1030"
          emissive={color}
          emissiveIntensity={0.35 + focus * 0.3}
          roughness={0.35}
          metalness={0.2}
          transparent
          opacity={0.92}
        />
      </mesh>
      <Particles count={count} color={color} agitation={norm + focus * 0.4} />
    </group>
  )
}
