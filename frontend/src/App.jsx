import { lazy, Suspense, useEffect, useRef } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useClerk, useSignIn, useSignUp } from '@clerk/react'
import MarketingLayout from './layouts/MarketingLayout'
import DashboardLayout from './layouts/DashboardLayout'
import ProtectedRoute from './auth/ProtectedRoute'
import LoadingScreen from './pages/LoadingScreen'

import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ForgotPassword from './pages/ForgotPassword'

const DashboardHome = lazy(() => import('./pages/DashboardHome'))
const AQIMonitor = lazy(() => import('./pages/AQIMonitor'))
const ForecastPage = lazy(() => import('./pages/ForecastPage'))
const DistrictExplorer = lazy(() => import('./pages/DistrictExplorer'))
const AQIMap = lazy(() => import('./pages/AQIMap'))
const StateOverview = lazy(() => import('./pages/StateOverview'))
const Leaderboard = lazy(() => import('./pages/Leaderboard'))
const PollutantAnalysis = lazy(() => import('./pages/PollutantAnalysis'))
const HealthAdvisory = lazy(() => import('./pages/HealthAdvisory'))
const ModelInsights = lazy(() => import('./pages/ModelInsights'))
const Settings = lazy(() => import('./pages/Settings'))
const FireImpact = lazy(() => import('./pages/FireImpact'))

// Completes the Future-API OAuth flow (signIn.sso()/signUp.sso() in
// AuthContext.jsx) - reads signIn.status/signUp.status off the same Future
// hooks those calls use and finalizes the session. This mirrors
// @clerk/react's own HandleSSOCallback logic (same conditions, same order),
// reimplemented inline because that component has no branch for the most
// common Google sign-in case: Clerk creates and activates the session
// entirely server-side ("no additional requirements needed"), so there's no
// pending signIn/signUp attempt left for it to finalize - the `clerk.session`
// check below handles exactly that case.
function SsoCallback() {
  const navigate = useNavigate()
  const clerk = useClerk()
  const { signIn } = useSignIn()
  const { signUp } = useSignUp()
  const hasRun = useRef(false)

  useEffect(() => {
    (async () => {
      if (!clerk.loaded || hasRun.current) return
      hasRun.current = true

      const goApp = () => navigate('/app', { replace: true })

      if (clerk.session) { goApp(); return }

      if (signIn.status === 'complete') {
        const { error } = await signIn.finalize({ navigate: async () => goApp() })
        if (error) console.error('[sso-callback] signIn.finalize() failed:', error)
        return
      }
      if (signUp.isTransferable) {
        const { error } = await signIn.create({ transfer: true })
        if (error) console.error('[sso-callback] signIn.create(transfer) failed:', error)
        if (signIn.status === 'complete') {
          const { error: fErr } = await signIn.finalize({ navigate: async () => goApp() })
          if (fErr) console.error('[sso-callback] finalize after transfer failed:', fErr)
          return
        }
        navigate('/login', { replace: true })
        return
      }
      if (signIn.status === 'needs_first_factor' &&
          !signIn.supportedFirstFactors?.every((f) => f.strategy === 'enterprise_sso')) {
        navigate('/login', { replace: true })
        return
      }
      if (signIn.isTransferable) {
        const { error } = await signUp.create({ transfer: true })
        if (error) console.error('[sso-callback] signUp.create(transfer) failed:', error)
        if (signUp.status === 'complete') {
          const { error: fErr } = await signUp.finalize({ navigate: async () => goApp() })
          if (fErr) console.error('[sso-callback] finalize after transfer failed:', fErr)
          return
        }
        navigate('/register', { replace: true })
        return
      }
      if (signUp.status === 'complete') {
        const { error } = await signUp.finalize({ navigate: async () => goApp() })
        if (error) console.error('[sso-callback] signUp.finalize() failed:', error)
        return
      }
      if (signIn.status === 'needs_second_factor' || signIn.status === 'needs_new_password') {
        navigate('/login', { replace: true })
        return
      }
      if (signIn.existingSession || signUp.existingSession) {
        const sessionId = signIn.existingSession?.sessionId || signUp.existingSession?.sessionId
        if (sessionId) {
          await clerk.setActive({ session: sessionId, navigate: async () => goApp() })
          return
        }
      }
      console.error('[sso-callback] no sign-in/sign-up state explained what to do next; ' +
        'sending to /login', { signInStatus: signIn.status, signUpStatus: signUp.status })
      navigate('/login', { replace: true })
    })()
  }, [clerk, clerk.loaded, signIn, signUp, navigate])

  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}>
      <div id="clerk-captcha" />
      <p style={{ color: '#888' }}>Completing sign-in…</p>
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route element={<MarketingLayout />}>
          <Route path="/" element={<LandingPage />} />
        </Route>

        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot" element={<ForgotPassword />} />
        <Route path="/sso-callback" element={<SsoCallback />} />

        <Route path="/app" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
          <Route index element={<DashboardHome />} />
          <Route path="monitor" element={<AQIMonitor />} />
          <Route path="forecast" element={<ForecastPage />} />
          <Route path="explorer" element={<DistrictExplorer />} />
          <Route path="map" element={<AQIMap />} />
          <Route path="state" element={<StateOverview />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="pollutants" element={<PollutantAnalysis />} />
          <Route path="fire" element={<FireImpact />} />
          <Route path="health" element={<HealthAdvisory />} />
          <Route path="models" element={<ModelInsights />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
