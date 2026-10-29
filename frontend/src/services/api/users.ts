import type { ListUsersQuery, Page, UserCreate, UserOut, UserUpdate } from '../../types/api'
import { apiGet, apiPatch, apiPost, withQuery } from './client'

export function listUsers(query: ListUsersQuery, signal?: AbortSignal): Promise<Page<UserOut>> {
  return apiGet<Page<UserOut>>(withQuery('/users', query), { signal })
}

export function createUser(body: UserCreate): Promise<UserOut> {
  return apiPost<UserOut>('/users', body)
}

export function updateUser(userId: number, body: UserUpdate): Promise<UserOut> {
  return apiPatch<UserOut>(`/users/${userId}`, body)
}
