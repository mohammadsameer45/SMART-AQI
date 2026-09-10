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
  dashboard: (state, area) => api.get(`/dashboard/${S(state, area)}`),
}

export const health = {
  advisory: (state, area) => api.get(`/health-advisory/${S(state, area)}`),
}

export const weather = {
  forArea: (state, area) => api.get(`/weather/${S(state, area)}`),
}

export const models = {
  metrics: () => api.get('/model-metrics'),
  insights: (model) => api.get(`/model-insights/${model}`),
}
