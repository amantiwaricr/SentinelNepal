import { createContext, useContext } from 'react'

import type { UserDirectoryEntry } from '../types/api'

export interface UserDirectoryValue {
  users: UserDirectoryEntry[]
  byId: Map<number, UserDirectoryEntry>
  reload: () => void
}

export const UserDirectoryContext = createContext<UserDirectoryValue>({
  users: [],
  byId: new Map(),
  reload: () => {},
})

export function useUserDirectory(): UserDirectoryValue {
  return useContext(UserDirectoryContext)
}

/** "sita" for a known id, "user #7" otherwise, "—" for none. */
export function useUserName(): (id: number | null | undefined) => string {
  const { byId } = useUserDirectory()
  return (id) => (id == null ? '—' : (byId.get(id)?.username ?? `user #${id}`))
}
