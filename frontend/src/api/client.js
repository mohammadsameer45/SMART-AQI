import axios from 'axios'

// Clerk owns the session; this is just a place for AuthContext to hand the
// axios client a way to fetch a fresh session token for each request (Clerk
// tokens are short-lived and auto-refreshing, so there's nothing to persist
// here ourselves - see auth/AuthContext.jsx's setTokenGetter call).
let getClerkToken = null
export const setTokenGetter = (fn) => { getClerkToken = fn }

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 20000,
})

api.interceptors.request.use(async (cfg) => {
  if (getClerkToken) {
    const t = await getClerkToken()
    if (t) cfg.headers.Authorization = `Bearer ${t}`
  }
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
    if (err.response?.status === 401 && !location.pathname.startsWith('/login')) {
      location.assign('/login')
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
