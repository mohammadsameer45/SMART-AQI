import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// Controllable fake Clerk state - tests import this and set `.isSignedIn`
// before rendering instead of touching localStorage (Clerk owns the real
// session, not us). `future` mirrors the useSignIn()/useSignUp() "Future"
// resource shape (see auth/AuthContext.jsx) with jest.fn() methods a test
// can override per-case (e.g. `clerkState.signIn.password.mockResolvedValue(...)`).
export const clerkState = {
  isSignedIn: false,
  signIn: {
    status: null, createdSessionId: null,
    password: vi.fn().mockResolvedValue({ error: null }),
    sso: vi.fn().mockResolvedValue({ error: null }),
    finalize: vi.fn().mockResolvedValue({ error: null }),
  },
  signUp: {
    status: null, createdSessionId: null,
    password: vi.fn().mockResolvedValue({ error: null }),
    finalize: vi.fn().mockResolvedValue({ error: null }),
    verifications: {
      sendEmailCode: vi.fn().mockResolvedValue({ error: null }),
      verifyEmailCode: vi.fn().mockResolvedValue({ error: null }),
    },
  },
}

vi.mock('@clerk/react', () => ({
  ClerkProvider: ({ children }) => children,
  useAuth: () => ({ isLoaded: true, isSignedIn: clerkState.isSignedIn, getToken: async () => 'test-token' }),
  useClerk: () => ({ signOut: vi.fn() }),
  useSignIn: () => ({ signIn: clerkState.signIn }),
  useSignUp: () => ({ signUp: clerkState.signUp }),
  AuthenticateWithRedirectCallback: () => null,
}))

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
