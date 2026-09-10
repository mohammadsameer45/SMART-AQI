import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * useApi(fn, deps) — runs an async endpoint call, tracks {data, loading, error}.
 * Re-runs when `deps` change. While `enabled` and no result has arrived yet it
 * reports `loading: true`, so a consumer's `if (loading) return <Loader/>` guard
 * always fires before it touches `data`.
 */
export function useApi(fn, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, loading: !!enabled, error: null })
  const fnRef = useRef(fn)
  fnRef.current = fn

  const run = useCallback(() => {
    let alive = true
    setState({ data: null, loading: true, error: null })
    Promise.resolve()
      .then(() => fnRef.current())
      .then((data) => { if (alive) setState({ data, loading: false, error: null }) })
      .catch((error) => { if (alive) setState({ data: null, loading: false, error }) })
    return () => { alive = false }
  }, [])

  useEffect(() => {
    if (!enabled) { setState({ data: null, loading: false, error: null }); return }
    return run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps.concat(enabled))

  const loading =
    state.loading || (enabled && state.data == null && state.error == null)

  return { data: state.data, error: state.error, loading, refetch: run }
}
