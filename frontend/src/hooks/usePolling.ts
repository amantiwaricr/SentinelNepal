import { useEffect } from 'react'

/** Calls `tick` every `intervalMs` while `active` (e.g. while an analysis run is queued). */
export function usePolling(tick: () => void, intervalMs: number, active: boolean) {
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(tick, intervalMs)
    return () => window.clearInterval(id)
  }, [tick, intervalMs, active])
}
