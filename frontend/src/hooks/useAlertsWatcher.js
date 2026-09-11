import { useEffect, useRef } from 'react'
import { alerts as alertsApi } from '../api/endpoints'
import { useToast } from './useToast'
import { currentPushState } from '../utils/push'

const CHECK_MS = 5 * 60 * 1000 // matches the live-feed refresh cadence

/**
 * Polls the current user's alert rules and surfaces newly-triggered ones as
 * an in-app toast, always. Each rule id only surfaces once per browser
 * session so it doesn't re-fire on every poll while still above threshold.
 *
 * A real OS-level notification is deliberately NOT fired from here when a
 * push subscription exists — scripts/check_alerts.py (run server-side by
 * refresh_worker.py) already sends a proper Web Push for that, which also
 * reaches the user with this tab closed. Firing a local Notification() too
 * would just duplicate it. If push isn't set up, this still fires a local
 * Notification as a same-tab-open fallback so alerts aren't silent.
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
      const pushState = await currentPushState().catch(() => 'unsupported')
      for (const r of rules) {
        if (!r.triggered || seen.current.has(r.id)) continue
        seen.current.add(r.id)
        const msg = `AQI in ${r.area}, ${r.state} is ${r.current_aqi} — above your alert threshold of ${r.threshold}.`
        toast.error(msg)
        if (pushState !== 'subscribed' && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
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
