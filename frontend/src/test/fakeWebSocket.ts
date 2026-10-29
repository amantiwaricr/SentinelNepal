/**
 * A stand-in for the browser WebSocket, installed for every test (jsdom's real one would try
 * to reach a server). Tests drive it: `FakeWebSocket.latest().open()` / `.send(event)`.
 */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  static latest(): FakeWebSocket {
    const socket = FakeWebSocket.instances.at(-1)
    if (!socket) throw new Error('No WebSocket was opened')
    return socket
  }

  static reset() {
    FakeWebSocket.instances = []
  }

  readonly url: string
  closed = false
  onopen: (() => void) | null = null
  onmessage: ((message: { data: unknown }) => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  open() {
    this.onopen?.()
  }

  /** Delivers a notification from the "server". */
  send(event: object) {
    this.onmessage?.({ data: JSON.stringify(event) })
  }

  /** The server or network closed the socket. */
  drop() {
    this.closed = true
    this.onclose?.()
  }

  close() {
    if (this.closed) return
    this.closed = true
    this.onclose?.()
  }
}
