import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import LoadingScreen from '../pages/LoadingScreen'

export default function ProtectedRoute({ children }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <LoadingScreen />
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return children
}
