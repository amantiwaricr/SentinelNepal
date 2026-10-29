import { vi } from 'vitest'

/** Stub window.fetch to answer every request with the same JSON response. */
export function mockFetchJson(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn().mockImplementation(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json', ...headers },
      }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
