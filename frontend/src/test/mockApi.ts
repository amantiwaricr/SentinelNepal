import { vi } from 'vitest'

import { API_BASE_URL } from '../config'
import type { UserOut } from '../types/api'
import { ANALYST } from './fixtures'

export interface MockRequest {
  method: string
  path: string
  query: URLSearchParams
  body: unknown
  params: Record<string, string>
}

export interface MockResponse {
  status: number
  body?: unknown
}

type Handler = (request: MockRequest) => unknown
/** A fixed response body; functions are handlers instead. */
type Fixed = object | string | number | boolean | null

/** Marks a handler result as a full response with a status code. */
export function respond(status: number, body?: unknown): MockResponse & { __response: true } {
  return { status, body, __response: true }
}

export function apiError(status: number, code: string, message: string) {
  return respond(status, { error: { code, message, details: null, request_id: 'req-test' } })
}

function isResponse(value: unknown): value is MockResponse {
  return typeof value === 'object' && value !== null && '__response' in value
}

function match(pattern: string, path: string): Record<string, string> | null {
  const names: string[] = []
  const regex = new RegExp(
    '^' +
      pattern.replace(/:[a-z_]+/g, (name) => {
        names.push(name.slice(1))
        return '([^/]+)'
      }) +
      '$',
  )
  const found = regex.exec(path)
  if (!found) return null
  return Object.fromEntries(names.map((name, i) => [name, decodeURIComponent(found[i + 1] ?? '')]))
}

/**
 * Replaces fetch with a small fake of the SentinelNepal API. Routes are "METHOD /path" with
 * optional ":param" segments; a value is returned as a 200 JSON body, a function computes it.
 * Unmocked requests fail loudly so tests cannot silently depend on missing data.
 * Signed in as `user` (default: an analyst) unless `user` is null.
 */
export function mockApi(
  routes: Record<string, Handler | Fixed>,
  { user = ANALYST }: { user?: UserOut | null } = {},
) {
  const calls: MockRequest[] = []
  const allRoutes: Record<string, Handler | Fixed> = {
    'GET /auth/me': user ?? apiError(401, 'unauthenticated', 'Not signed in'),
    'GET /users/directory': user ? [user] : [],
    'POST /auth/logout': respond(204),
    ...routes,
  }

  const fetchMock = vi.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input, 'http://localhost')
    const path = url.pathname.slice(API_BASE_URL.length)
    const method = (init.method ?? 'GET').toUpperCase()
    let body: unknown = init.body
    if (typeof init.body === 'string') body = JSON.parse(init.body)
    for (const [key, handler] of Object.entries(allRoutes)) {
      const [routeMethod, routePath] = key.split(' ') as [string, string]
      const params = routeMethod === method ? match(routePath, path) : null
      if (!params) continue
      const request = { method, path, query: url.searchParams, body, params }
      calls.push(request)
      const result = typeof handler === 'function' ? (handler as Handler)(request) : handler
      const { status, body: responseBody } = isResponse(result)
        ? result
        : { status: 200, body: result }
      return new Response(
        status === 204 || responseBody === undefined ? null : JSON.stringify(responseBody),
        { status, headers: { 'Content-Type': 'application/json' } },
      )
    }
    throw new Error(`Unmocked API request: ${method} ${path}${url.search}`)
  })
  vi.stubGlobal('fetch', fetchMock)

  return {
    calls,
    /** Requests made to one route, e.g. callsTo('PATCH', '/alerts/7'). */
    callsTo: (method: string, path: string) =>
      calls.filter((c) => c.method === method && c.path === path),
  }
}
