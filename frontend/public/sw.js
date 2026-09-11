// SMART AQI service worker — Web Push delivery for threshold alerts only.
// No caching/offline behavior is implemented; this exists solely so the
// browser can wake the page-less worker to show a push notification.

self.addEventListener('push', (event) => {
  let payload = { title: 'SMART AQI alert', body: 'An air-quality alert triggered.', url: '/app/settings' }
  try { if (event.data) payload = { ...payload, ...event.data.json() } } catch { /* use defaults */ }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      data: { url: payload.url || '/app/settings' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data?.url || '/app/settings'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && 'focus' in client) return client.focus()
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    }),
  )
})
