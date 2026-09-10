import { Link } from 'react-router-dom'
import SceneCanvas from '../three/SceneCanvas'
import AtmosphereSphere from '../three/AtmosphereSphere'
import './auth.css'

export default function ForgotPassword() {
  return (
    <div className="auth-page">
      <SceneCanvas className="auth-canvas" camera={{ position: [0, 0, 6], fov: 52 }}
        fallback={<div className="auth-fallback" />}>
        <AtmosphereSphere aqi={60} />
      </SceneCanvas>
      <div className="auth-card glass">
        <Link to="/" className="brand" style={{ marginBottom: 18 }}>
          <span className="brand-mark" /> SMART <span className="brand-thin">AQI</span>
        </Link>
        <h1 className="auth-title">Reset password</h1>
        <p className="muted tiny" style={{ marginTop: 10 }}>
          Password reset by email is not enabled in this build. Contact the
          administrator to reset your account, or create a new one.
        </p>
        <div className="auth-alt tiny" style={{ marginTop: 18 }}>
          <Link to="/login">Back to log in</Link>
          <Link to="/register">Create account</Link>
        </div>
      </div>
    </div>
  )
}
