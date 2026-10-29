import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../services/api/client'

export type ResourceState<T> =
  { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: ApiError }

export function toApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError(0, 'unexpected_error', 'An unexpected error occurred')
}

/**
 * Loads one API resource with loading/error states and a manual reload. `load` must be
 * stable (module function or useCallback); a new function triggers a new request.
 * `reload({ quiet: true })` refreshes without showing the loading state (used by polling).
 */
export function useApiResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [prevLoad, setPrevLoad] = useState(() => load)

  // A new loader (e.g. changed filters) shows the loading state for the new request.
  if (prevLoad !== load) {
    setPrevLoad(() => load)
    setState({ status: 'loading' })
  }

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => setState({ status: 'success', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({ status: 'error', error: toApiError(error) })
      })
    return () => controller.abort()
  }, [load, attempt])

  const reload = useCallback((options: { quiet?: boolean } = {}) => {
    if (!options.quiet) setState({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  return { state, reload }
}
