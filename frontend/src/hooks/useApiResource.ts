import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../services/api/client'

export type ResourceState<T> =
  { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: ApiError }

/** Loads one API resource with loading/error states and a manual reload. */
export function useApiResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => setState({ status: 'success', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({
          status: 'error',
          error:
            error instanceof ApiError
              ? error
              : new ApiError(0, 'unexpected_error', 'An unexpected error occurred'),
        })
      })
    return () => controller.abort()
  }, [load, attempt])

  const reload = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  return { state, reload }
}
