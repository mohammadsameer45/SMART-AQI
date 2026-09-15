import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '../auth/AuthContext'
import { ToastProvider } from '../hooks/useToast'
import { clerkState } from './setup'

const me = vi.fn()
vi.mock('../api/endpoints', () => ({
  auth: { me: (...a) => me(...a) },
  geo: { states: vi.fn().mockResolvedValue([]), areas: vi.fn().mockResolvedValue({ level: 'city', items: [] }) },
  aqi: {}, health: {}, models: {},
}))

import LoginPage from '../pages/LoginPage'
import ProtectedRoute from '../auth/ProtectedRoute'

function shell(ui, route = '/login') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={ui} />
            <Route path="/app" element={<div>DASHBOARD</div>} />
            <Route path="/app/secret" element={
              <ProtectedRoute><div>SECRET</div></ProtectedRoute>
            } />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  clerkState.isSignedIn = false
  clerkState.signIn.status = null
  clerkState.signIn.createdSessionId = null
})

describe('LoginPage', () => {
  it('renders the form fields', () => {
    shell(<LoginPage />)
    expect(screen.getByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('submits credentials and lands on the dashboard route', async () => {
    clerkState.signIn.password.mockImplementation(async () => {
      clerkState.signIn.status = 'complete'
      return { error: null }
    })
    clerkState.signIn.finalize.mockImplementation(async () => {
      clerkState.isSignedIn = true
      return { error: null }
    })
    me.mockResolvedValue({ user: { email: 'a@b.com', name: 'A' } })
    const u = userEvent.setup()
    shell(<LoginPage />)
    await u.type(screen.getByLabelText('Email'), 'a@b.com')
    await u.type(screen.getByLabelText('Password'), 'Str0ng#Pass1')
    await u.click(screen.getByRole('button', { name: /log in/i }))
    await waitFor(() => expect(clerkState.signIn.password)
      .toHaveBeenCalledWith({ emailAddress: 'a@b.com', password: 'Str0ng#Pass1' }))
    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument()
  })

  it('shows the server error and stays on the page', async () => {
    clerkState.signIn.password.mockResolvedValue({
      error: { message: 'Incorrect email or password' },
    })
    const u = userEvent.setup()
    shell(<LoginPage />)
    await u.type(screen.getByLabelText('Email'), 'a@b.com')
    await u.type(screen.getByLabelText('Password'), 'whatever1A#')
    await u.click(screen.getByRole('button', { name: /log in/i }))
    // message appears both inline and as a toast
    const hits = await screen.findAllByText(/incorrect email or password/i)
    expect(hits.length).toBeGreaterThan(0)
    expect(screen.queryByText('DASHBOARD')).not.toBeInTheDocument()
  })
})

describe('ProtectedRoute', () => {
  it('redirects to /login when there is no valid session', async () => {
    clerkState.isSignedIn = false
    shell(<LoginPage />, '/app/secret')
    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
    expect(screen.queryByText('SECRET')).not.toBeInTheDocument()
  })

  it('renders children when the session is valid', async () => {
    clerkState.isSignedIn = true
    me.mockResolvedValue({ user: { email: 'a@b.com', name: 'A' } })
    shell(<LoginPage />, '/app/secret')
    expect(await screen.findByText('SECRET')).toBeInTheDocument()
  })
})
