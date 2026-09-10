import axios from 'axios'

const TOKEN_KEY = 'smartaqi_token'

export const tokenStore = {
  get: () => {
    try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  set: (t) => { try { localStorage.setItem(TOKEN_KEY, t) } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ } },
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 20000,
})

api.interceptors.request.use((cfg) => {
  const t = tokenStore.get()
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

// Unwrap the {ok,data|error} envelope; turn errors into thrown Error(message)
api.interceptors.response.use(
  (res) => {
    if (res.data && res.data.ok === false) {
      return Promise.reject(new ApiError(res.data.error))
    }
    return res.data?.data ?? res.data
  },
  (err) => {
    const e = err.response?.data?.error
    if (err.response?.status === 401) {
      tokenStore.clear()
      if (!location.pathname.startsWith('/login')) {
        location.assign('/login')
      }
    }
    return Promise.reject(new ApiError(e || { code: 'network', message: err.message }))
  },
)

export class ApiError extends Error {
  constructor({ code, message }) {
    super(message || 'Request failed')
    this.code = code
  }
}

export default api
