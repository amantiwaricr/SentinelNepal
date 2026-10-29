import { createContext, useContext, useEffect, useRef } from 'react'

import { API_BASE_URL } from '../config'

/**
 * A notification from /api/v1/events. Notifications only say that something changed; pages
 * refetch the data over REST, which stays the source of truth. `resync` is sent locally
 * after a reconnect, because notifications sent while disconnected were missed.
 */
export interface LiveEvent {
  type: string
  [key: string]: unknown
}

/** The WebSocket URL for the API base (relative bases resolve against this page). */
export function eventsUrl(base: string = API_BASE_URL, page: string = window.location.href) {
  const url = new URL(`${base}/events`, page)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

export type LiveEventListener = (event: LiveEvent) => void

export interface LiveEventsValue {
  connected: boolean
  subscribe: (listener: LiveEventListener) => () => void
}

export const LiveEventsContext = createContext<LiveEventsValue | null>(null)

/** Connection state of the notification socket (false outside the provider). */
export function useLiveConnection(): boolean {
  return useContext(LiveEventsContext)?.connected ?? false
}

/** Event types after which alert lists and counts may have changed. */
export const ALERT_EVENTS = ['alert.created', 'alerts.created', 'resync'] as const

/**
 * Calls `refresh` when any of `types` arrives, at most once per `delayMs` (a busy lab can
 * send many notifications a second; one refetch covers them all).
 */
export function useRefreshOn(types: readonly string[], refresh: () => void, delayMs = 1000) {
  const subscribe = useContext(LiveEventsContext)?.subscribe
  const refreshRef = useRef(refresh)
  useEffect(() => {
    refreshRef.current = refresh
  })
  const key = types.join(',')

  useEffect(() => {
    if (!subscribe) return
    const wanted = new Set(key.split(','))
    let timer: number | undefined
    const unsubscribe = subscribe((event) => {
      if (!wanted.has(event.type) || timer !== undefined) return
      timer = window.setTimeout(() => {
        timer = undefined
        refreshRef.current()
      }, delayMs)
    })
    return () => {
      unsubscribe()
      window.clearTimeout(timer)
    }
  }, [subscribe, key, delayMs])
}
