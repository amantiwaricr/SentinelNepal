import type { LoginIn, UserDirectoryEntry, UserOut } from '../../types/api'
import { apiGet, apiPost } from './client'

export function login(body: LoginIn): Promise<UserOut> {
  return apiPost<UserOut>('/auth/login', body)
}

export function logout(): Promise<void> {
  return apiPost<void>('/auth/logout')
}

export function getCurrentUser(signal?: AbortSignal): Promise<UserOut> {
  return apiGet<UserOut>('/auth/me', { signal })
}

export function getUserDirectory(signal?: AbortSignal): Promise<UserDirectoryEntry[]> {
  return apiGet<UserDirectoryEntry[]>('/users/directory', { signal })
}
