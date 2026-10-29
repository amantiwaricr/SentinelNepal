import { API_BASE_URL } from '../../config'
import type { ApiErrorBody } from '../../types/api'

/** An error response from the API, or a failure to reach it (status 0). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown
  readonly requestId: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    details: unknown = null,
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const error = (value as { error: unknown }).error
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

/**
 * Called when a request is rejected with 401 (expired or revoked session), so the app can
 * return to the sign-in page. Returns a function that removes the handler.
 */
export function onUnauthorized(handler: UnauthorizedHandler): () => void {
  unauthorizedHandler = handler
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null
  }
}

type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue>

/** Appends the non-empty parameters as a query string. */
export function withQuery(path: string, params: object = {}): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params as QueryParams)) {
    if (value === undefined || value === null || value === '') continue
    search.append(key, String(value))
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** JSON-serialised unless it is FormData (file uploads). */
  body?: unknown
  /** Non-2xx statuses whose JSON body is a normal response, e.g. 503 from /health/ready. */
  acceptStatuses?: number[]
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, acceptStatuses = [], headers, ...init } = options
  const isForm = body instanceof FormData
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      // The session cookie is HttpOnly and SameSite=Strict; the dev server and production
      // deployment serve the API from the same origin, so no cross-site credentials.
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        // Required by the backend on state-changing requests (CSRF defence).
        'X-Requested-With': 'SentinelNepal',
        ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Could not reach the SentinelNepal API')
  }

  // 204 No Content (e.g. logout) has no body to parse.
  if (response.status === 204) return undefined as T
  const payload: unknown = await response.json().catch(() => null)

  if (response.ok || acceptStatuses.includes(response.status)) {
    if (payload === null) {
      throw new ApiError(response.status, 'invalid_response', 'The API returned an empty response')
    }
    return payload as T
  }

  if (response.status === 401) unauthorizedHandler?.()

  if (isErrorBody(payload)) {
    const { code, message, details, request_id } = payload.error
    throw new ApiError(response.status, code, message, details, request_id)
  }
  throw new ApiError(
    response.status,
    'http_error',
    `Request failed with status ${response.status}`,
    null,
    response.headers.get('X-Request-ID'),
  )
}

type ReadOptions = Omit<RequestOptions, 'method' | 'body'>

export function apiGet<T>(path: string, options: ReadOptions = {}) {
  return apiRequest<T>(path, { ...options, method: 'GET' })
}

export function apiPost<T>(path: string, body?: unknown, options: ReadOptions = {}) {
  return apiRequest<T>(path, { ...options, method: 'POST', body })
}

export function apiPatch<T>(path: string, body: unknown, options: ReadOptions = {}) {
  return apiRequest<T>(path, { ...options, method: 'PATCH', body })
}
