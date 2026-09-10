import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// jsdom has no WebGL — replace the 3D scene wrapper and scenes with inert stubs.
vi.mock('../three/SceneCanvas', () => ({
  default: ({ fallback }) => fallback ?? null,
}))
vi.mock('../three/AtmosphereSphere', () => ({ default: () => null }))
vi.mock('../three/PollutantColumns', () => ({ default: () => null }))
vi.mock('../three/ForecastRibbon', () => ({ default: () => null }))

// Recharts ResponsiveContainer needs a measured box in jsdom.
class RO { observe() {} unobserve() {} disconnect() {} }
global.ResizeObserver = RO
window.matchMedia = window.matchMedia || ((q) => ({
  matches: false, media: q, onchange: null,
  addListener() {}, removeListener() {},
  addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false },
}))

// deterministic localStorage
let store = {}
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v) },
    removeItem: (k) => { delete store[k] },
    clear: () => { store = {} },
  },
  configurable: true,
})
