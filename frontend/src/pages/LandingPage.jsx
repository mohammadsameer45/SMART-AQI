import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import SceneCanvas from '../three/SceneCanvas'
import AtmosphereSphere from '../three/AtmosphereSphere'
import './landing.css'

const rise = {
  hidden: { opacity: 0, y: 24 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.6, ease: [0.22, 1, 0.36, 1] } }),
}

function Reveal({ children, i = 0, className }) {
  return (
    <motion.div className={className} variants={rise} custom={i}
      initial="hidden" whileInView="show" viewport={{ once: true, margin: '-80px' }}>
      {children}
    </motion.div>
  )
}

const FEATURES = [
  ['Live AQI intelligence', 'Current index and pollutant concentrations for every monitoring city with real data — no fabricated readings, no empty placeholders.'],
  ['7-day AQI forecasting', 'Recursive multi-step predictions with an uncertainty band that widens by horizon. Clearly labelled as predictions, never measurements.'],
  ['Four-model AI engine', 'XGBoost, LSTM, GRU and a time-series Transformer trained on a chronological split. The best model is chosen automatically by validation error.'],
  ['Health advisory', 'CPCB-category guidance for the general population and for people with asthma or respiratory sensitivity — precautionary, not medical.'],
  ['District intelligence', 'Drill from state to district to station. Only areas backed by legitimate cleaned data are shown.'],
  ['Real 3D visualisation', 'Browser-native Three.js scenes — an atmospheric particle field, 3D pollutant columns and a 3D forecast ribbon.'],
]

const STACK = ['React + Vite', 'Three.js / R3F', 'Flask REST API', 'MongoDB', 'scikit-learn', 'TensorFlow / Keras', 'XGBoost', 'Recharts']

export default function LandingPage() {
  const heroRef = useRef()
  return (
    <div className="landing" ref={heroRef}>
      {/* ---------------- HERO ---------------- */}
      <section className="hero">
        <SceneCanvas className="hero-canvas" camera={{ position: [0, 0, 6.4], fov: 50 }}
          fallback={<div className="hero-fallback" />}>
          <AtmosphereSphere aqi={168} />
        </SceneCanvas>
        <div className="container hero-inner">
          <motion.div initial="hidden" animate="show" variants={rise} custom={0} className="eyebrow">
            Global-grade air quality intelligence · India
          </motion.div>
          <motion.h1 initial="hidden" animate="show" variants={rise} custom={1} className="hero-title">
            See the air.<br />Understand the risk.<br /><span>Predict what comes next.</span>
          </motion.h1>
          <motion.p initial="hidden" animate="show" variants={rise} custom={2} className="hero-sub">
            SMART AQI monitors, visualises and forecasts air quality across Indian
            states and districts — with a four-model AI engine and precautionary
            health guidance for sensitive groups.
          </motion.p>
          <motion.div initial="hidden" animate="show" variants={rise} custom={3} className="hero-cta">
            <Link to="/login" className="btn btn-primary">Explore Air Quality</Link>
            <a href="#forecast" className="btn btn-ghost">View Forecast ↓</a>
          </motion.div>
          <motion.div initial="hidden" animate="show" variants={rise} custom={4} className="hero-stats">
            <div><b>21</b><span>states with data</span></div>
            <div><b>110</b><span>monitoring stations</span></div>
            <div><b>2.35M</b><span>cleaned hourly rows</span></div>
            <div><b>4</b><span>AI models compared</span></div>
          </motion.div>
        </div>
      </section>

      {/* ---------------- FEATURES ---------------- */}
      <section id="features" className="container section">
        <Reveal><div className="eyebrow">Why SMART AQI</div></Reveal>
        <Reveal i={1}><h2 className="section-h">Built on real data, honest about its limits</h2></Reveal>
        <div className="feat-grid">
          {FEATURES.map(([t, d], i) => (
            <Reveal key={t} i={i % 3} className="feat-card glass">
              <h3>{t}</h3><p className="muted tiny">{d}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------------- FORECAST ---------------- */}
      <section id="forecast" className="container section two-col">
        <div>
          <Reveal><div className="eyebrow">7-Day Forecasting</div></Reveal>
          <Reveal i={1}><h2 className="section-h">Know tomorrow’s air today</h2></Reveal>
          <Reveal i={2}><p className="muted">
            Every eligible station gets a recursive seven-day AQI forecast with a
            per-horizon confidence band. Where a location lacks enough history,
            SMART AQI says so — it never invents a curve.
          </p></Reveal>
          <Reveal i={3}>
            <ul className="tick-list">
              <li>Chronological train / validation / test split — no leakage</li>
              <li>Best model chosen by validation MAE, not hard-coded</li>
              <li>Predictions clearly separated from measurements</li>
            </ul>
          </Reveal>
        </div>
        <Reveal i={2} className="glass forecast-preview">
          <SceneCanvas className="mini-canvas" camera={{ position: [0, 1.5, 7], fov: 45 }}>
            <AtmosphereSphere aqi={92} />
          </SceneCanvas>
        </Reveal>
      </section>

      {/* ---------------- INSIGHTS ---------------- */}
      <section id="insights" className="container section">
        <Reveal><div className="eyebrow">AI Model Comparison</div></Reveal>
        <Reveal i={1}><h2 className="section-h">Four models, one honest scoreboard</h2></Reveal>
        <Reveal i={2}><p className="muted" style={{ maxWidth: 640 }}>
          XGBoost, LSTM, GRU and a genuine time-series Transformer (positional
          encoding + multi-head attention) are trained on the same split and
          scored on MAE, RMSE, R² and MAPE. The Model Insights screen shows the
          full table, feature importance and actual-vs-predicted scatter.
        </p></Reveal>
      </section>

      {/* ---------------- TECHNOLOGY ---------------- */}
      <section id="technology" className="container section">
        <Reveal><div className="eyebrow">Technology</div></Reveal>
        <Reveal i={1}><h2 className="section-h">A production-style stack</h2></Reveal>
        <div className="stack-row">
          {STACK.map((s, i) => (
            <Reveal key={s} i={i % 4} className="stack-chip">{s}</Reveal>
          ))}
        </div>
      </section>

      {/* ---------------- CTA ---------------- */}
      <section id="about" className="container section">
        <Reveal className="cta glass">
          <h2>Ready to explore the air around you?</h2>
          <p className="muted">Create an account and open the dashboard.</p>
          <div className="hero-cta" style={{ justifyContent: 'center' }}>
            <Link to="/register" className="btn btn-primary">Create account</Link>
            <Link to="/login" className="btn btn-ghost">Log in</Link>
          </div>
        </Reveal>
      </section>
    </div>
  )
}
