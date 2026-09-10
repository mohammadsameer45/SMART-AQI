# SMART AQI — UI / UX

## Aesthetic

Dark, premium, futuristic. Deep-charcoal backgrounds, violet/indigo gradients,
soft glow, white display type, selective glassmorphism. Hand-written CSS only —
**no Tailwind, no CSS framework**. Tokens in `frontend/src/styles/tokens.css`;
base primitives (`.glass`, `.btn`, `.field`, `.eyebrow`, `.container`) in
`base.css`; feature CSS colocated per area.

Fonts: **Space Grotesk** (display) + **Inter** (body), via Google Fonts.

AQI category colours are semantic and follow CPCB, never the brand violet:
Good `#2e9e4f` · Satisfactory `#7bb93f` · Moderate `#f0c030` · Poor `#f08b24` ·
Very Poor `#e24b4b` · Severe `#8b2e8b`.

## Structure

```
frontend/src/
  main.jsx            providers: Router · Toast · Auth
  App.jsx             routes + lazy-loaded dashboard pages
  api/                axios client (envelope unwrap, 401 handling) + endpoints
  auth/               AuthContext, ProtectedRoute
  components/         AQIGauge, AreaPicker, SelectionContext, ui/Bits
  layouts/            MarketingLayout (nav+footer), DashboardLayout (sidebar+topbar)
  three/              SceneCanvas, AtmosphereSphere, PollutantColumns, ForecastRibbon
  charts/             Recharts wrappers (history, forecast, trends, compare, scatter)
  hooks/              useApi, useToast
  pages/              Landing, Login, Register, Forgot, LoadingScreen,
                      DashboardHome, AQIMonitor, ForecastPage, DistrictExplorer,
                      PollutantAnalysis, HealthAdvisory, ModelInsights, Settings
  styles/             tokens.css, base.css
```

## Pages

| Route | Page | Highlights |
|---|---|---|
| `/` | Landing | 3D atmosphere hero, staggered Framer Motion reveals, feature grid, forecast/insights/tech sections, CTA |
| `/login`, `/register` | Auth | full-bleed 3D `AtmosphereSphere` that reacts to field focus; password-strength meter; JWT stored in `localStorage` |
| `/app` | Overview | animated `AQIGauge`, stat tiles, 90-day history area chart, 7-day forecast, advisory summary |
| `/app/monitor` | AQI Monitor | gauge + pollutant snapshot + per-station table + range-toggle history |
| `/app/forecast` | Forecast | **3D `ForecastRibbon`** (orbit/zoom, uncertainty whiskers) + 2D band chart + day table |
| `/app/state` | State Overview | per-state avg/current AQI, AQI-category distribution bar, best/worst district tables, monthly-mean trend chart |
| `/app/explorer` | District Explorer | prominent state→area picker, coverage tiles, gauge, history, forecast, monitoring-location table |
| `/app/pollutants` | Pollutant Analysis | **3D `PollutantColumns`** + per-pollutant cards + multi-series trend |
| `/app/health` | Health Advisory | status / who-should-care / outdoor / respiratory / tomorrow / 7-day outlook cards + disclaimer |
| `/app/models` | Model Insights | comparison table (best highlighted), metric bar chart, actual-vs-predicted scatter, feature importance |
| `/app/settings` | Settings | profile, data notes, logout |

## 3D (Three.js / React Three Fiber / drei)

`SceneCanvas` wraps every `<Canvas>`: DPR capped at 1.8, high-performance GL,
and it renders only a static fallback when `prefers-reduced-motion` is set.
Scenes are lazy (pages are `React.lazy`). Genuine 3D:

- **AtmosphereSphere** — 1.4k–4k additive-blended particles on a sphere around an
  emissive core; count/colour/agitation scale with an AQI value; pointer
  parallax; `focus` prop pulses the core when an auth field is focused.
- **PollutantColumns** — animated 3D bars (X = pollutant, Y = concentration),
  billboarded labels, `OrbitControls`.
- **ForecastRibbon** — 3D bars per horizon day with uncertainty whiskers and a
  connecting polyline; gentle auto-rotation + orbit controls.
- **IndiaMap3D** (3D AQI Map page) — real geoBoundaries ADM1/ADM2 polygons
  extruded with `THREE.ExtrudeGeometry`; bar height + colour = current AQI,
  grey and flat where there is no data. Hover raises the region and shows an
  `<Html>` tooltip; click a state drills into its districts (and sets the
  global state/area selection). GeoJSON comes slimmed (simplify + round,
  ~300 KB) from `GET /api/map/india` and `/api/map/state/:state`, cached
  5 min server-side.

## Motion

Framer Motion for landing reveals (staggered, `whileInView`, `once`). GSAP is
available but the current build leans on Framer + CSS transitions. All motion
respects `prefers-reduced-motion` (global CSS kill-switch + SceneCanvas guard).

## Accessibility

Keyboard-navigable controls, visible `:focus-visible` ring, labelled form
fields and selects, semantic headings, AA-contrast text tokens, toast messages
in an `aria-live` region, reduced-motion support.

## State & data

- `AuthContext` — token in `localStorage` (`try/catch` guarded), `axios`
  interceptor attaches it, a `401` clears it and redirects to `/login`.
- `SelectionContext` (inside `DashboardLayout`) — shared `state` / `area`
  selection, persisted to `localStorage`, drives every dashboard page.
- `useApi(fn, deps)` — `{data, loading, error, refetch}` with abort-safe
  updates.

## Honesty in the UI

- "Latest available historical value" banner wherever `is_live === false`.
- Forecast screens carry a "predictions, not measurements" banner and per-day
  category comes from the shared CPCB table.
- Areas with no forecast show an explanatory empty state — never fabricated
  numbers.
- Footer + Settings: data provenance and "not medical advice".
