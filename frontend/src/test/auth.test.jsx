import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '../auth/AuthContext'
import { ToastProvider } from '../hooks/useToast'

const login = vi.fn()
const register = vi.fn()
const me = vi.fn()
vi.mock('../api/endpoints', () => ({
  auth: {
    login: (...a) => login(...a),
    register: (...a) => register(...a),
    me: (...a) => me(...a),
  },
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

beforeEach(() => { vi.clearAllMocks(); window.localStorage.clear() })

describe('LoginPage', () => {
  it('renders the form fields', () => {
    shell(<LoginPage />)
    expect(screen.getByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('submits credentials and lands on the dashboard route', async () => {
    login.mockResolvedValue({ token: 't', user: { email: 'a@b.com', name: 'A' } })
    const u = userEvent.setup()
    shell(<LoginPage />)
    await u.type(screen.getByLabelText('Email'), 'a@b.com')
    await u.type(screen.getByLabelText('Password'), 'Str0ng#Pass1')
    await u.click(screen.getByRole('button', { name: /log in/i }))
    await waitFor(() => expect(login).toHaveBeenCalledWith({ email: 'a@b.com', password: 'Str0ng#Pass1' }))
    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument()
  })

  it('shows the server error and stays on the page', async () => {
    login.mockRejectedValue(new Error('Incorrect email or password'))
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
    me.mockRejectedValue(new Error('no token'))
    shell(<LoginPage />, '/app/secret')
    expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument()
    expect(screen.queryByText('SECRET')).not.toBeInTheDocument()
  })

  it('renders children when the session is valid', async () => {
    window.localStorage.setItem('smartaqi_token', 'tok')
    me.mockResolvedValue({ user: { email: 'a@b.com', name: 'A' } })
    shell(<LoginPage />, '/app/secret')
    expect(await screen.findByText('SECRET')).toBeInTheDocument()
  })
})
