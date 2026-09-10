import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { OrbitControls, Text, Billboard } from '@react-three/drei'

/** 3D pollutant bars: X = pollutant, Y = concentration, colour = load. */
function Bar({ x, value, max, label, color }) {
  const ref = useRef()
  const target = Math.max((value / max) * 3.2, 0.02)
  useFrame((_, dt) => {
    if (!ref.current) return
    ref.current.scale.y += (target - ref.current.scale.y) * Math.min(dt * 4, 1)
    ref.current.position.y = ref.current.scale.y / 2
  })
  return (
    <group position={[x, 0, 0]}>
      <mesh ref={ref} scale={[1, 0.02, 1]}>
        <boxGeometry args={[0.55, 1, 0.55]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.25} roughness={0.4} />
      </mesh>
      <Billboard position={[0, -0.42, 0]}>
        <Text fontSize={0.19} color="#a1a1aa" anchorX="center">{label}</Text>
      </Billboard>
      <Billboard position={[0, target + 0.32, 0]}>
        <Text fontSize={0.2} color="#ffffff" anchorX="center">
          {value == null ? '—' : Math.round(value)}
        </Text>
      </Billboard>
    </group>
  )
}

export default function PollutantColumns({ data = [] }) {
  const items = data.filter((d) => d.value != null)
  const max = Math.max(...items.map((d) => d.value), 1)
  const span = Math.max(items.length - 1, 1)
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 8, 5]} intensity={1.4} />
      <group position={[0, -1.2, 0]}>
        {items.map((d, i) => (
          <Bar
            key={d.label}
            x={(i - span / 2) * 0.9}
            value={d.value}
            max={max}
            label={d.label}
            color={d.color || '#8b5cf6'}
          />
        ))}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
          <planeGeometry args={[span * 0.9 + 1.4, 2.4]} />
          <meshStandardMaterial color="#0d0d15" transparent opacity={0.5} />
        </mesh>
      </group>
      <OrbitControls enablePan={false} minDistance={4} maxDistance={11}
        maxPolarAngle={Math.PI / 2.05} />
    </>
  )
}
