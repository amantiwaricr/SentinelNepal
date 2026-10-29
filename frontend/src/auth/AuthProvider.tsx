import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import * as authApi from '../services/api/auth'
import { ApiError, onUnauthorized } from '../services/api/client'
import type { LoginIn } from '../types/api'
import { AuthContext, type AuthState } from './AuthContext'

/**
 * Holds who is signed in. The session itself is an HttpOnly cookie the browser sends
 * automatically; the frontend never sees or stores the token. On start-up it asks the API
 * (`/auth/me`) whether the cookie is still valid.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'checking' })

  useEffect(() => {
    const controller = new AbortController()
    authApi
      .getCurrentUser(controller.signal)
      .then((user) => setState({ status: 'authenticated', user }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        // 401 means "not signed in"; any other failure also leaves the user signed out,
        // and the sign-in page reports API errors when they try again.
        if (!(error instanceof ApiError) || error.status !== 401) console.warn(error)
        setState({ status: 'anonymous' })
      })
    return () => controller.abort()
  }, [])

  // Any 401 after sign-in means the session expired or was revoked (e.g. password reset).
  useEffect(
    () =>
      onUnauthorized(() =>
        setState((current) =>
          current.status === 'authenticated' ? { status: 'anonymous', reason: 'expired' } : current,
        ),
      ),
    [],
  )

  const login = useCallback(async (credentials: LoginIn) => {
    const user = await authApi.login(credentials)
    setState({ status: 'authenticated', user })
    return user
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      // Even if the request fails, forget the user locally; the server session then
      // expires on its own idle timeout.
      setState({ status: 'anonymous', reason: 'signed_out' })
    }
  }, [])

  const value = useMemo(() => ({ state, login, logout }), [state, login, logout])
  return <AuthContext value={value}>{children}</AuthContext>
}
