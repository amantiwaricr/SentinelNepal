import { useCallback, useState } from 'react'

import type { ApiError } from '../services/api/client'
import { toApiError } from './useApiResource'

/** Runs a state-changing API call, tracking pending and error state for the form. */
export function useAction<A extends unknown[], R>(action: (...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      setPending(true)
      setError(null)
      try {
        return await action(...args)
      } catch (caught) {
        setError(toApiError(caught))
        return undefined
      } finally {
        setPending(false)
      }
    },
    [action],
  )

  return { run, pending, error, clearError: () => setError(null) }
}
