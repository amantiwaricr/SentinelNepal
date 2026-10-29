import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { FakeWebSocket } from './fakeWebSocket'

// jsdom has no layout engine; Recharts' ResponsiveContainer needs ResizeObserver to exist.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

// Assigned directly (not vi.stubGlobal) so it survives unstubGlobals between tests.
globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket

afterEach(() => {
  cleanup()
  FakeWebSocket.reset()
})
