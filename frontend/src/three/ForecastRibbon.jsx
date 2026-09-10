import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { OrbitControls, Text, Billboard, Line } from '@react-three/drei'
import { aqiColor } from '../utils/aqi'

/** 3D 7-day forecast: X = day, Y = predicted AQI, ribbon = uncertainty band. */
export default function ForecastRibbon({ days = [] }) {
  const group = useRef()
  useFrame((state) => {
    if (group.current) group.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.15) * 0.25
  })
  if (!days.length) return null
  const maxV = Math.max(...days.map((d) => d.upper ?? d.predicted_AQI), 100)
  const H = 3.4
  const y = (v) => (v / maxV) * H
  const x = (i) => (i - (days.length - 1) / 2) * 1.15

  const linePts = days.map((d, i) => [x(i), y(d.predicted_AQI), 0])

  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 6, 6]} intensity={1.3} />
      <group ref={group} position={[0, -1.5, 0]}>
        {days.map((d, i) => (
          <group key={i} position={[x(i), 0, 0]}>
            <mesh position={[0, y(d.predicted_AQI) / 2, 0]}>
              <boxGeometry args={[0.34, Math.max(y(d.predicted_AQI), 0.02), 0.34]} />
              <meshStandardMaterial color={aqiColor(d.predicted_AQI)}
                emissive={aqiColor(d.predicted_AQI)} emissiveIntensity={0.3} />
            </mesh>
            {/* uncertainty whisker */}
            <Line points={[[0, y(d.lower ?? d.predicted_AQI), 0], [0, y(d.upper ?? d.predicted_AQI), 0]]}
              color="#a78bfa" lineWidth={2} transparent opacity={0.6} />
            <Billboard position={[0, -0.35, 0]}>
              <Text fontSize={0.17} color="#a1a1aa" anchorX="center">{`+${i + 1}d`}</Text>
            </Billboard>
            <Billboard position={[0, y(d.predicted_AQI) + 0.3, 0]}>
              <Text fontSize={0.18} color="#fff" anchorX="center">{Math.round(d.predicted_AQI)}</Text>
            </Billboard>
          </group>
        ))}
        <Line points={linePts} color="#ffffff" lineWidth={1.5} transparent opacity={0.4} />
      </group>
      <OrbitControls enablePan={false} minDistance={5} maxDistance={12}
        maxPolarAngle={Math.PI / 2.05} />
    </>
  )
}
