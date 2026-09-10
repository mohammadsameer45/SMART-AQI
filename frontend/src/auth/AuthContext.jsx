import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { auth as authApi } from '../api/endpoints'
import { tokenStore } from '../api/client'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let alive = true
    if (!tokenStore.get()) { setReady(true); return }
    authApi.me()
      .then((d) => { if (alive) setUser(d.user) })
      .catch(() => tokenStore.clear())
      .finally(() => { if (alive) setReady(true) })
    return () => { alive = false }
  }, [])

  const login = useCallback(async (body) => {
    const d = await authApi.login(body)
    tokenStore.set(d.token); setUser(d.user); return d.user
  }, [])

  const register = useCallback(async (body) => {
    const d = await authApi.register(body)
    tokenStore.set(d.token); setUser(d.user); return d.user
  }, [])

  const logout = useCallback(() => { tokenStore.clear(); setUser(null) }, [])

  return (
    <AuthCtx.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
