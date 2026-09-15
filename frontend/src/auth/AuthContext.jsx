import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useAuth as useClerkAuth, useClerk, useSignIn, useSignUp } from '@clerk/react'
import { auth as authApi } from '../api/endpoints'
import { setTokenGetter } from '../api/client'

const AuthCtx = createContext(null)

/**
 * Thin adapter over Clerk so the rest of the app (ProtectedRoute,
 * DashboardLayout, Settings, ...) keeps using the same
 * {user, ready, login, register, loginWithGoogle, logout} shape it always
 * has - only the internals are backed by Clerk's useSignIn/useSignUp "Future"
 * API instead of our own register/login endpoints. `user` is our own small
 * profile object (GET /api/auth/me), not Clerk's raw user - Clerk owns
 * identity, our backend just confirms the session and shapes the response.
 *
 * `isSignedIn` (Clerk's own truth) and `ready` are deliberately independent
 * of whether the `/api/auth/me` profile fetch has succeeded - a route guard
 * must trust Clerk's session, not a backend call that can transiently fail
 * (e.g. a token-getter race right after a fresh sign-in) and incorrectly
 * bounce an actually-authenticated user back to /login. The profile fetch
 * only fills in `user` for display; ProtectedRoute checks `isSignedIn`.
 */
export function AuthProvider({ children }) {
  const { isLoaded: authLoaded, isSignedIn, getToken } = useClerkAuth()
  const { signOut } = useClerk()
  const { signIn } = useSignIn()
  const { signUp } = useSignUp()

  const [profile, setProfile] = useState(null)

  useEffect(() => {
    setTokenGetter(isSignedIn ? getToken : null)
  }, [isSignedIn, getToken])

  useEffect(() => {
    let alive = true
    if (!authLoaded || !isSignedIn) { setProfile(null); return }
    authApi.me()
      .then((d) => { if (alive) setProfile(d.user) })
      .catch(() => { if (alive) setProfile(null) })
    return () => { alive = false }
  }, [authLoaded, isSignedIn])

  const login = useCallback(async ({ email, password }) => {
    const { error } = await signIn.password({ emailAddress: email, password })
    if (error) throw new Error(error.message || 'Incorrect email or password')
    if (signIn.status !== 'complete') {
      throw new Error('Additional verification is required for this account')
    }
    const { error: finalizeError } = await signIn.finalize()
    if (finalizeError) throw new Error(finalizeError.message || 'Could not complete sign-in')
  }, [signIn])

  const loginWithGoogle = useCallback(async () => {
    const { error } = await signIn.sso({
      strategy: 'oauth_google',
      redirectUrl: '/sso-callback',
      redirectCallbackUrl: '/sso-callback',
    })
    if (error) throw new Error(error.message || 'Could not start Google sign-in')
  }, [signIn])

  // register(): creates the Clerk sign-up and (if the Clerk dashboard
  // requires it, which is the default) sends an email verification code.
  // Returns {needsVerification} so RegisterPage knows whether to show the
  // code-entry step or the account is already active.
  const register = useCallback(async ({ name, email, password }) => {
    const [firstName, ...rest] = name.trim().split(/\s+/)
    const { error } = await signUp.password({
      emailAddress: email, password, firstName, lastName: rest.join(' ') || undefined,
    })
    if (error) throw new Error(error.message || 'Could not create account')
    if (signUp.status === 'complete') {
      const { error: finalizeError } = await signUp.finalize()
      if (finalizeError) throw new Error(finalizeError.message || 'Could not complete sign-up')
      return { needsVerification: false }
    }
    const { error: codeError } = await signUp.verifications.sendEmailCode()
    if (codeError) throw new Error(codeError.message || 'Could not send verification email')
    return { needsVerification: true }
  }, [signUp])

  const verifyRegistration = useCallback(async (code) => {
    const { error } = await signUp.verifications.verifyEmailCode({ code })
    if (error) throw new Error(error.message || 'Incorrect or expired code')
    if (signUp.status !== 'complete') throw new Error('Incorrect or expired code')
    const { error: finalizeError } = await signUp.finalize()
    if (finalizeError) throw new Error(finalizeError.message || 'Could not complete sign-up')
  }, [signUp])

  const logout = useCallback(() => signOut(), [signOut])

  return (
    <AuthCtx.Provider value={{
      user: profile, ready: authLoaded, isSignedIn: !!isSignedIn,
      login, register, verifyRegistration, loginWithGoogle, logout,
    }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
