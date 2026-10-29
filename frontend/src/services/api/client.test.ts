import { describe, expect, it, vi } from 'vitest'

import { mockFetchJson } from '../../test/helpers'
import { ApiError, apiGet, apiPost, onUnauthorized, withQuery } from './client'

describe('apiGet', () => {
  it('returns the JSON body on success and sends the API headers', async () => {
    const fetchMock = mockFetchJson(200, { status: 'ok' })
    await expect(apiGet('/health/live')).resolves.toEqual({ status: 'ok' })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v1/health/live')
    expect(init.credentials).toBe('same-origin')
    expect(init.headers).toMatchObject({ 'X-Requested-With': 'SentinelNepal' })
  })

  it('converts the backend error envelope into an ApiError', async () => {
    mockFetchJson(404, {
      error: { code: 'not_found', message: 'Not Found', details: null, request_id: 'abc-123' },
    })
    const error = await apiGet('/missing').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 404,
      code: 'not_found',
      message: 'Not Found',
      requestId: 'abc-123',
    })
  })

  it('reports a generic error when the body is not an error envelope', async () => {
    mockFetchJson(502, { unexpected: true }, { 'X-Request-ID': 'proxy-req-1' })
    await expect(apiGet('/x')).rejects.toMatchObject({
      status: 502,
      code: 'http_error',
      requestId: 'proxy-req-1',
    })
  })

  it('accepts an explicitly allowed non-2xx status as data', async () => {
    mockFetchJson(503, { status: 'not_ready' })
    await expect(apiGet('/health/ready', { acceptStatuses: [503] })).resolves.toEqual({
      status: 'not_ready',
    })
  })
})

describe('request helpers', () => {
  it('builds query strings without empty values', () => {
    expect(withQuery('/alerts', { src_ip: '10.0.0.1', status: undefined, cidr: '', page: 2 })).toBe(
      '/alerts?src_ip=10.0.0.1&page=2',
    )
    expect(withQuery('/alerts', {})).toBe('/alerts')
  })

  it('sends JSON bodies with a content type', async () => {
    const fetchMock = mockFetchJson(200, { id: 1 })
    await apiPost('/incidents', { title: 'x' })
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"title":"x"}')
    expect(init.headers).toMatchObject({ 'Content-Type': 'application/json' })
  })

  it('sends FormData as-is so the browser sets the multipart boundary', async () => {
    const fetchMock = mockFetchJson(202, { id: 1 })
    const form = new FormData()
    form.append('file', new Blob(['a,b']), 'x.csv')
    await apiPost('/datasets/analyses', form)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.body).toBe(form)
    expect(init.headers).not.toHaveProperty('Content-Type')
    expect(init.headers).toMatchObject({ 'X-Requested-With': 'SentinelNepal' })
  })

  it('returns nothing for 204 responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    await expect(apiPost('/auth/logout')).resolves.toBeUndefined()
  })

  it('notifies the registered handler on 401 and stops after unregistering', async () => {
    const handler = vi.fn()
    const remove = onUnauthorized(handler)
    mockFetchJson(401, {
      error: { code: 'unauthenticated', message: 'Sign in', details: null, request_id: null },
    })
    await expect(apiGet('/alerts')).rejects.toMatchObject({ status: 401 })
    expect(handler).toHaveBeenCalledTimes(1)
    remove()
    await expect(apiGet('/alerts')).rejects.toMatchObject({ status: 401 })
    expect(handler).toHaveBeenCalledTimes(1)
  })
})
