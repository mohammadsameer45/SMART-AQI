import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
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
