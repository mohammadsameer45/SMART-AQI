import './loading.css'

export default function LoadingScreen({ text = 'Mapping the air around you…' }) {
  return (
    <div className="loading-screen">
      <div className="ls-orb">
        <span /><span /><span />
      </div>
      <div className="ls-brand">SMART <b>AQI</b></div>
      <div className="ls-text muted tiny">{text}</div>
    </div>
  )
}
