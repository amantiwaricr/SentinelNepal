import { describe, expect, it } from 'vitest'

import { mockFetchJson } from '../../test/helpers'
import { ApiError, apiGet } from './client'

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
