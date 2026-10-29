import { createContext, useContext } from 'react'

import type { LoginIn, UserOut } from '../types/api'

export type AuthState =
  | { status: 'checking' }
  | { status: 'anonymous'; reason?: 'expired' | 'signed_out' }
  | { status: 'authenticated'; user: UserOut }

export interface AuthContextValue {
  state: AuthState
  login: (credentials: LoginIn) => Promise<UserOut>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

/** The signed-in user; only valid on routes wrapped in <RequireAuth>. */
export function useCurrentUser(): UserOut {
  const { state } = useAuth()
  if (state.status !== 'authenticated') throw new Error('No signed-in user')
  return state.user
}
