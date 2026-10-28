import { vi } from 'vitest'

/** Stub window.fetch to return one JSON response. */
export function mockFetchJson(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json', ...headers },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
