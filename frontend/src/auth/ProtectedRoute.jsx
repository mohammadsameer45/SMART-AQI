import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import LoadingScreen from '../pages/LoadingScreen'

export default function ProtectedRoute({ children }) {
  // Gate on Clerk's own isSignedIn, not on whether the /api/auth/me profile
  // fetch has succeeded - that call can transiently fail right after a
  // fresh sign-in and must not bounce an actually-authenticated user out.
  const { isSignedIn, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <LoadingScreen />
  if (!isSignedIn) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return children
}
