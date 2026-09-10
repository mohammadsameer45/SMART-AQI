import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import SceneCanvas from '../three/SceneCanvas'
import AtmosphereSphere from '../three/AtmosphereSphere'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../hooks/useToast'
import './auth.css'

export default function LoginPage() {
  const { login } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const loc = useLocation()
  const [form, setForm] = useState({ email: '', password: '' })
  const [focus, setFocus] = useState(0)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      await login(form)
      toast.success('Welcome back')
      nav(loc.state?.from || '/app', { replace: true })
    } catch (e2) {
      setErr(e2.message); toast.error(e2.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="auth-page">
      <SceneCanvas className="auth-canvas" camera={{ position: [0, 0, 6], fov: 52 }}
        fallback={<div className="auth-fallback" />}>
        <AtmosphereSphere aqi={140} focus={focus} />
      </SceneCanvas>

      <div className="auth-card glass">
        <Link to="/" className="brand" style={{ marginBottom: 20 }}>
          <span className="brand-mark" /> SMART <span className="brand-thin">AQI</span>
        </Link>
        <h1 className="auth-title">Welcome back</h1>
        <p className="muted tiny" style={{ marginBottom: 22 }}>Log in to open your dashboard.</p>

        <form onSubmit={submit} className="auth-form">
          <div className="field">
            <label htmlFor="login-email">Email</label>
            <input id="login-email" type="email" autoComplete="email" required value={form.email}
              onChange={set('email')} onFocus={() => setFocus(0.6)} onBlur={() => setFocus(0)} />
          </div>
          <div className="field">
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" autoComplete="current-password" required value={form.password}
              onChange={set('password')} onFocus={() => setFocus(1)} onBlur={() => setFocus(0)} />
          </div>
          {err && <div className="err">{err}</div>}
          <button className="btn btn-primary" disabled={busy} style={{ width: '100%', justifyContent: 'center' }}>
            {busy ? <span className="spin" /> : 'Log in'}
          </button>
        </form>

        <div className="auth-alt tiny">
          <Link to="/forgot">Forgot password?</Link>
          <span>New here? <Link to="/register">Create an account</Link></span>
        </div>
      </div>
    </div>
  )
}
