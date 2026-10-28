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

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** Non-2xx statuses whose JSON body is a normal response, e.g. 503 from /health/ready. */
  acceptStatuses?: number[]
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, acceptStatuses = [], headers, ...init } = options
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      // Session cookies are added in Phase 3; same-origin keeps them HttpOnly and SameSite.
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        // Required by the backend on state-changing requests (CSRF defence, Phase 3).
        'X-Requested-With': 'SentinelNepal',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Could not reach the SentinelNepal API')
  }

  const payload: unknown = await response.json().catch(() => null)

  if (response.ok || acceptStatuses.includes(response.status)) {
    if (payload === null) {
      throw new ApiError(response.status, 'invalid_response', 'The API returned an empty response')
    }
    return payload as T
  }

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

export function apiGet<T>(path: string, options: Omit<RequestOptions, 'method' | 'body'> = {}) {
  return apiRequest<T>(path, { ...options, method: 'GET' })
}
