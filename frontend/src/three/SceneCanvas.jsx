import { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'

const reduced =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * Thin wrapper around <Canvas>: capped DPR, graceful fallback, and it renders
 * nothing (just the fallback) when the user prefers reduced motion.
 */
export default function SceneCanvas({
  children,
  camera = { position: [0, 0, 6], fov: 50 },
  className,
  fallback = null,
  frameloop = 'always',
  style,
}) {
  if (reduced) return <div className={className} style={style}>{fallback}</div>
  return (
    <div className={className} style={style}>
      <Canvas
        dpr={[1, 1.8]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        camera={camera}
        frameloop={frameloop}
      >
        <Suspense fallback={null}>{children}</Suspense>
      </Canvas>
    </div>
  )
}
