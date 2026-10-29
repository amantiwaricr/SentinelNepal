import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import {
  eventsUrl,
  LiveEventsContext,
  type LiveEvent,
  type LiveEventListener,
} from './liveEventsContext'

const MAX_RETRY_MS = 30_000

function parseEvent(data: unknown): LiveEvent | null {
  if (typeof data !== 'string') return null
  try {
    const value: unknown = JSON.parse(data)
    if (typeof value === 'object' && value !== null && 'type' in value) {
      return typeof value.type === 'string' ? (value as LiveEvent) : null
    }
  } catch {
    // Malformed notifications are ignored; the next REST refresh shows the real state.
  }
  return null
}

/**
 * Keeps one notification socket open while signed in and reconnects with exponential
 * backoff (1 s, 2 s, 4 s … 30 s). The browser sends the session cookie with the handshake;
 * the backend checks it and the page's Origin.
 */
export function LiveEventsProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false)
  const listeners = useRef(new Set<LiveEventListener>())

  useEffect(() => {
    let socket: WebSocket | null = null
    let retryTimer: number | undefined
    let failures = 0
    let wasConnected = false
    let stopped = false

    const emit = (event: LiveEvent) => {
      for (const listener of listeners.current) listener(event)
    }

    const connect = () => {
      socket = new WebSocket(eventsUrl())
      socket.onopen = () => {
        failures = 0
        setConnected(true)
        if (wasConnected) emit({ type: 'resync' })
        wasConnected = true
      }
      socket.onmessage = (message: MessageEvent) => {
        const event = parseEvent(message.data)
        if (event) emit(event)
      }
      socket.onclose = () => {
        setConnected(false)
        if (stopped) return
        retryTimer = window.setTimeout(connect, Math.min(MAX_RETRY_MS, 1000 * 2 ** failures))
        failures += 1
      }
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retryTimer)
      socket?.close()
    }
  }, [])

  // Stable, so subscribers do not resubscribe (and lose a pending refresh) when the
  // connection state changes.
  const subscribe = useCallback((listener: LiveEventListener) => {
    listeners.current.add(listener)
    return () => {
      listeners.current.delete(listener)
    }
  }, [])
  const value = useMemo(() => ({ connected, subscribe }), [connected, subscribe])

  return <LiveEventsContext.Provider value={value}>{children}</LiveEventsContext.Provider>
}
