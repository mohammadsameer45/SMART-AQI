import { useEffect, useRef } from 'react'
import { alerts as alertsApi } from '../api/endpoints'
import { useToast } from './useToast'

const CHECK_MS = 5 * 60 * 1000 // matches the live-feed refresh cadence

/**
 * Polls the current user's alert rules and surfaces newly-triggered ones as
 * a toast + (if permitted) a real browser Notification. Each rule id is
 * only surfaced once per browser session so it doesn't re-fire on every
 * poll while still above threshold.
 */
export function useAlertsWatcher() {
  const toast = useToast()
  const seen = useRef(new Set())

  useEffect(() => {
    let alive = true
    const check = async () => {
      let rules
      try { rules = await alertsApi.list() } catch { return }
      if (!alive) return
      for (const r of rules) {
        if (!r.triggered || seen.current.has(r.id)) continue
        seen.current.add(r.id)
        const msg = `AQI in ${r.area}, ${r.state} is ${r.current_aqi} — above your alert threshold of ${r.threshold}.`
        toast.error(msg)
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          try { new Notification('SMART AQI alert', { body: msg }) } catch { /* ignore */ }
        }
      }
    }
    check()
    const id = setInterval(check, CHECK_MS)
    return () => { alive = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
