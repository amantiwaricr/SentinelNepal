import { useMemo, type ReactNode } from 'react'

import { useApiResource } from '../hooks/useApiResource'
import { getUserDirectory } from '../services/api/auth'
import { UserDirectoryContext } from './userDirectoryContext'

/** Loads colleague names once per session, for assignment pickers and "who did this". */
export function UserDirectoryProvider({ children }: { children: ReactNode }) {
  const { state, reload } = useApiResource(getUserDirectory)
  const value = useMemo(() => {
    const users = state.status === 'success' ? state.data : []
    return { users, byId: new Map(users.map((u) => [u.id, u])), reload }
  }, [state, reload])
  return <UserDirectoryContext value={value}>{children}</UserDirectoryContext>
}
