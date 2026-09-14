import api from './client'

export const auth = {
  register: (body) => api.post('/auth/register', body),
  login: (body) => api.post('/auth/login', body),
  me: () => api.get('/auth/me'),
}

export const geo = {
  states: () => api.get('/states'),
  areas: (state) => api.get(`/states/${encodeURIComponent(state)}/districts`),
  locations: (state, area) =>
    api.get(`/districts/${encodeURIComponent(state)}/${encodeURIComponent(area)}/locations`),
  overview: (state) => api.get(`/states/${encodeURIComponent(state)}/overview`),
}

const S = (state, area) =>
  `${encodeURIComponent(state)}/${encodeURIComponent(area)}`

export const aqi = {
  current: (state, area) => api.get(`/aqi/current/${S(state, area)}`),
  history: (state, area, params) => api.get(`/aqi/history/${S(state, area)}`, { params }),
  forecast: (state, area, model) =>
    api.get(`/aqi/forecast/${S(state, area)}`, { params: model ? { model } : {} }),
  pollutants: (state, area) => api.get(`/pollutants/${S(state, area)}`),
  pollutantWhy: (state, area, pollutant) =>
    api.get(`/pollutants/${S(state, area)}/${encodeURIComponent(pollutant)}/why`),
  dashboard: (state, area) => api.get(`/dashboard/${S(state, area)}`),
  trend: (state, area) => api.get(`/aqi/trend/${S(state, area)}`),
  spike: (state, area) => api.get(`/aqi/spike/${S(state, area)}`),
  explanation: (state, area) => api.get(`/aqi/explanation/${S(state, area)}`),
  sourceAnalysis: (state, area) => api.get(`/aqi/source-analysis/${S(state, area)}`),
  impact: (state, area) => api.get(`/aqi/impact/${S(state, area)}`),
  whyChange: (state, area, body = {}) => api.post('/aqi/why-change', { state, area, ...body }),
  events: (state, area) => api.get(`/aqi/events/${S(state, area)}`),
  forecast24h: (state, area) => api.get(`/aqi/forecast-24h/${S(state, area)}`),
  outdoorPlanner: (state, area) => api.get(`/aqi/outdoor-planner/${S(state, area)}`),
  recovery: (state, area) => api.get(`/aqi/recovery/${S(state, area)}`),
}

export const health = {
  advisory: (state, area) => api.get(`/health-advisory/${S(state, area)}`),
}

export const weather = {
  forArea: (state, area) => api.get(`/weather/${S(state, area)}`),
  dispersion: (state, area) => api.get(`/dispersion/${S(state, area)}`),
}

export const models = {
  metrics: () => api.get('/model-metrics'),
  insights: (model) => api.get(`/model-insights/${model}`),
}

export const leaderboard = {
  national: () => api.get('/leaderboard'),
  compare: (pairs) => api.get('/compare', { params: { areas: pairs.join(',') } }),
}

export const alerts = {
  list: () => api.get('/alerts'),
  create: (state, area, threshold) => api.post('/alerts', { state, area, threshold }),
  remove: (id) => api.delete(`/alerts/${id}`),
}
