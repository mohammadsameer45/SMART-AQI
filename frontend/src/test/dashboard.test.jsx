import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from './render'

// stub the chart wrappers — we test page composition, not Recharts internals
vi.mock('../charts/charts', () => ({
  HistoryChart: () => <div data-testid="history-chart" />,
  ForecastChart: () => <div data-testid="forecast-chart" />,
  PollutantTrend: () => <div data-testid="pollutant-trend" />,
  ModelCompareChart: () => <div data-testid="model-compare" />,
  ActualVsPredicted: () => <div data-testid="avp" />,
}))

const DASH = {
  state: 'Delhi', area: 'Delhi',
  coverage: { matched_level: 'city', n_stations: 3, total_records: 2009, history_end: '2020-07-01' },
  current: {
    available: true, is_live: false, as_of: '2020-07-01', AQI: 142, AQI_display: 142,
    AQI_bucket: 'Moderate', source_note: 'Latest available historical value.',
    pollutants: { PM25: 71, PM10: 128, NO2: 34, O3: 38 },
  },
  history_90d: [{ date: '2020-06-01', AQI: 130 }, { date: '2020-06-02', AQI: 150 }],
  forecast: {
    forecast_available: true, model: 'baseline',
    days: [{ horizon_day: 1, forecast_date: '2020-07-02', predicted_AQI: 145, lower: 110, upper: 180 }],
  },
  advisory: {
    available: true, current_bucket: 'Moderate', air_quality_status: 'Acceptable for most.',
    outdoor_activity: 'General population can continue normal activity.',
    respiratory_precautions: ['Keep medication available', 'Monitor symptoms'],
    disclaimer: 'General precautionary guidance only. SMART AQI does not diagnose.',
  },
}

const dashboard = vi.fn()
const states = vi.fn().mockResolvedValue(['Delhi', 'Kerala'])
const areas = vi.fn().mockResolvedValue({ level: 'city', items: ['Delhi'] })
vi.mock('../api/endpoints', () => ({
  aqi: { dashboard: (...a) => dashboard(...a) },
  geo: { states: (...a) => states(...a), areas: (...a) => areas(...a) },
  auth: { me: vi.fn().mockRejectedValue(new Error('no token')) },
}))

import DashboardHome from '../pages/DashboardHome'
import { SelectionProvider } from '../components/SelectionContext'
import AreaPicker from '../components/AreaPicker'

beforeEach(() => { vi.clearAllMocks(); window.localStorage.clear() })

describe('DashboardHome', () => {
  it('renders the current AQI, forecast and advisory from the composite payload', async () => {
    dashboard.mockResolvedValue(DASH)
    renderWithProviders(
      <SelectionProvider><DashboardHome /></SelectionProvider>,
    )
    expect(await screen.findByText('142')).toBeInTheDocument()          // gauge number
    expect(screen.getAllByText(/moderate/i).length).toBeGreaterThan(0)   // category chip
    expect(screen.getByTestId('history-chart')).toBeInTheDocument()
    expect(screen.getByTestId('forecast-chart')).toBeInTheDocument()
    expect(screen.getByText(/acceptable for most/i)).toBeInTheDocument()
    expect(screen.getByText(/latest available historical value/i)).toBeInTheDocument()
  })

  it('shows an error state when the API rejects', async () => {
    dashboard.mockRejectedValue(new Error('boom'))
    renderWithProviders(<SelectionProvider><DashboardHome /></SelectionProvider>)
    expect(await screen.findByText(/couldn.t load this/i)).toBeInTheDocument()
  })
})

describe('AreaPicker / SelectionContext', () => {
  it('populates the state selector and lets you change state', async () => {
    const u = userEvent.setup()
    renderWithProviders(<SelectionProvider><AreaPicker /></SelectionProvider>)
    const stateSel = await screen.findByRole('combobox', { name: /state/i })
    await waitFor(() => expect(stateSel).toHaveValue('Delhi'))
    expect(states).toHaveBeenCalled()
    await u.selectOptions(stateSel, 'Kerala')
    await waitFor(() => expect(areas).toHaveBeenCalledWith('Kerala'))
  })
})
