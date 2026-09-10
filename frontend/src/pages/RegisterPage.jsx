import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import SceneCanvas from '../three/SceneCanvas'
import AtmosphereSphere from '../three/AtmosphereSphere'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../hooks/useToast'
import './auth.css'

function strength(pw) {
  let s = 0
  if (pw.length >= 8) s++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++
  if (/\d/.test(pw)) s++
  if (/[^A-Za-z0-9]/.test(pw)) s++
  return s
}

export default function RegisterPage() {
  const { register } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const [f, setF] = useState({ name: '', email: '', password: '', confirm_password: '' })
  const [focus, setFocus] = useState(0)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }))
  const sc = useMemo(() => strength(f.password), [f.password])

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    if (f.password !== f.confirm_password) { setErr('Passwords do not match'); return }
    if (sc < 3) { setErr('Use at least 3 of: lowercase, uppercase, digit, symbol (min 8 chars)'); return }
    setBusy(true)
    try {
      await register(f)
      toast.success('Account created')
      nav('/app', { replace: true })
    } catch (e2) { setErr(e2.message); toast.error(e2.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="auth-page">
      <SceneCanvas className="auth-canvas" camera={{ position: [0, 0, 6], fov: 52 }}
        fallback={<div className="auth-fallback" />}>
        <AtmosphereSphere aqi={90} focus={focus} />
      </SceneCanvas>

      <div className="auth-card glass">
        <Link to="/" className="brand" style={{ marginBottom: 18 }}>
          <span className="brand-mark" /> SMART <span className="brand-thin">AQI</span>
        </Link>
        <h1 className="auth-title">Create your account</h1>
        <p className="muted tiny" style={{ marginBottom: 20 }}>Free — takes a few seconds.</p>

        <form onSubmit={submit} className="auth-form">
          <div className="field">
            <label htmlFor="reg-name">Name</label>
            <input id="reg-name" required value={f.name} onChange={set('name')}
              onFocus={() => setFocus(0.4)} onBlur={() => setFocus(0)} />
          </div>
          <div className="field">
            <label htmlFor="reg-email">Email</label>
            <input id="reg-email" type="email" autoComplete="email" required value={f.email} onChange={set('email')}
              onFocus={() => setFocus(0.6)} onBlur={() => setFocus(0)} />
          </div>
          <div className="field">
            <label htmlFor="reg-password">Password</label>
            <input id="reg-password" type="password" autoComplete="new-password" required value={f.password} onChange={set('password')}
              onFocus={() => setFocus(1)} onBlur={() => setFocus(0)} />
            <div className="pw-meter"><span style={{ width: `${sc * 25}%` }} data-s={sc} /></div>
          </div>
          <div className="field">
            <label htmlFor="reg-confirm">Confirm password</label>
            <input id="reg-confirm" type="password" autoComplete="new-password" required value={f.confirm_password}
              onChange={set('confirm_password')} onFocus={() => setFocus(1)} onBlur={() => setFocus(0)} />
          </div>
          {err && <div className="err">{err}</div>}
          <button className="btn btn-primary" disabled={busy} style={{ width: '100%', justifyContent: 'center' }}>
            {busy ? <span className="spin" /> : 'Create account'}
          </button>
        </form>
        <div className="auth-alt tiny">
          <span>Already have an account? <Link to="/login">Log in</Link></span>
        </div>
      </div>
    </div>
  )
}
