import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { LoadingState } from '../components/LoadingState'
import type { Role } from '../types/api'
import { useAuth } from './AuthContext'

/**
 * Route guard. This is a convenience for the user only: every API endpoint checks the
 * session and role on the server, so hiding a page here is never the security boundary.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { state } = useAuth()
  const location = useLocation()

  if (state.status === 'checking') return <LoadingState label="Checking your session…" />
  if (state.status === 'anonymous') {
    const next = `${location.pathname}${location.search}`
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(next)}`}
        replace
        state={{ reason: state.reason }}
      />
    )
  }
  return children
}

export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { state } = useAuth()
  if (state.status === 'authenticated' && state.user.role !== role) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h1 className="text-xl font-semibold text-slate-900">Not available for your role</h1>
        <p className="mt-2 text-sm text-slate-600">
          This page needs the <strong>{role}</strong> role. Ask an administrator if you need access.
        </p>
      </section>
    )
  }
  return children
}
