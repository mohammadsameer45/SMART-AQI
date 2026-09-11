import api from '../api/client'

export const pushSupported = () =>
  typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window

function urlBase64ToUint8Array(base64) {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64)
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)))
}

/** Registers the service worker once (idempotent, safe to call on every page load). */
export async function registerServiceWorker() {
  if (!pushSupported()) return null
  try { return await navigator.serviceWorker.register('/sw.js') }
  catch { return null }
}

/** Requests Notification permission, subscribes to push, and saves the
 * subscription on the backend. Returns true if fully enabled. */
export async function enablePush() {
  if (!pushSupported()) return false
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return false

  const reg = await registerServiceWorker()
  if (!reg) return false

  const { key } = await api.get('/push/vapid-public-key')
  if (!key) return false

  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    })
  }
  await api.post('/push/subscribe', sub.toJSON())
  return true
}

export async function currentPushState() {
  if (!pushSupported()) return 'unsupported'
  if (Notification.permission !== 'granted') return Notification.permission
  const reg = await navigator.serviceWorker.getRegistration()
  const sub = reg && (await reg.pushManager.getSubscription())
  return sub ? 'subscribed' : 'granted'
}
