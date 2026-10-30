/** Live monitoring page and live notifications. Collectors, flows and addresses are SYNTHETIC. */
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { LiveEventsProvider } from '../events/LiveEventsProvider'
import { eventsUrl, useLiveConnection, useRefreshOn } from '../events/liveEventsContext'
import { FakeWebSocket } from '../test/fakeWebSocket'
import { ADMIN, COMPONENTS, EMPTY_DASHBOARD } from '../test/fixtures'
import { apiError, mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'
import type { CollectorOut, LiveStatusOut, RecentFlowOut } from '../types/api'

const CLOSED_GATE: LiveStatusOut = {
  live_model_profile: 'full_no_ttl',
  model: {
    id: 2,
    feature_profile: 'full_no_ttl',
    name: 'random_forest',
    version: 'synthetic',
  },
  alert_threshold: 0.2,
  compatible: true,
  unavailable_features: [],
  approximate_features: ['swin', 'sjit'],
  approved: false,
  model_ready: false,
  reason: 'The live model random_forest synthetic is not approved for live inference.',
  collectors_total: 1,
  collectors_online: 1,
  collectors_scoring: 0,
  queue_batches: 0,
}

const COLLECTOR: CollectorOut = {
  id: 1,
  name: 'lab-sensor',
  mode: 'observation',
  online: true,
  last_heartbeat_at: '2026-10-29T16:00:00Z',
  records_received: 346,
  records_rejected: 26,
  records_dropped: 0,
  records_processed: 320,
  alerts_created: 0,
  last_error: null,
  heartbeat_stats: { packets: 1060, open_flows: 1, capture_files_failed: 0 },
  created_at: '2026-10-29T15:00:00Z',
}

const FLOW: RecentFlowOut = {
  collector_id: 1,
  source: 'live',
  observed_at: '2026-10-29T16:00:01Z',
  src_ip: '192.0.2.3',
  src_port: 58596,
  dst_ip: '192.0.2.2',
  dst_port: 80,
  proto: 'tcp',
  service: 'http',
  state: 'FIN',
  dur: 0.0008,
  spkts: 6,
  dpkts: 4,
  sbytes: 403,
  dbytes: 471,
  scored: false,
}

function liveRoutes(overrides: Record<string, unknown> = {}) {
  return {
    'GET /live/status': CLOSED_GATE,
    'GET /collectors': [COLLECTOR],
    'GET /live/flows': [FLOW],
    ...overrides,
  }
}

describe('LiveMonitoringPage', () => {
  it('shows the gate, collector counters and flows from the API', async () => {
    mockApi(liveRoutes())
    renderAppAt('/live')
    expect(await screen.findByText(CLOSED_GATE.reason)).toBeInTheDocument()
    expect(screen.getByText('Live scoring off')).toBeInTheDocument()
    expect(screen.getByText(/suspicions, not proof/)).toBeInTheDocument()
    expect(await screen.findByText('lab-sensor')).toBeInTheDocument()
    expect(screen.getByText('Online')).toBeInTheDocument()
    expect(screen.getByText('Records received').nextElementSibling).toHaveTextContent('346')
    expect(screen.getByText('Packets read').nextElementSibling).toHaveTextContent('1,060')
    const flows = await screen.findByRole('table', { name: 'Recent flows' })
    const row = within(flows).getByText('192.0.2.3:58596').closest('tr')
    expect(row).toHaveTextContent('Live')
    expect(row).toHaveTextContent('tcp / http')
    expect(row).toHaveTextContent('Not scored')
  })

  it('shows the uncalibrated score of scored flows, alerted or not', async () => {
    mockApi(
      liveRoutes({
        'GET /live/flows': [
          { ...FLOW, scored: true, attack_score: 0.312, top_attack_category: 'Reconnaissance' },
          { ...FLOW, src_port: 40001, scored: true, attack_score: null },
        ],
      }),
    )
    renderAppAt('/live')
    const flows = await screen.findByRole('table', { name: 'Recent flows' })
    const scored = within(flows).getByText('192.0.2.3:58596').closest('tr')
    expect(scored).toHaveTextContent('0.312')
    expect(scored).toHaveTextContent('leans Reconnaissance')
    const rejected = within(flows).getByText('192.0.2.3:40001').closest('tr')
    expect(rejected).toHaveTextContent('Rejected by model')
    // Analysts see the state but cannot change collector modes.
    expect(screen.queryByRole('button', { name: /Switch to/ })).not.toBeInTheDocument()
  })

  it('explains how to start when nothing is registered yet', async () => {
    mockApi(
      liveRoutes({
        'GET /live/status': { ...CLOSED_GATE, model: null, collectors_total: 0 },
        'GET /collectors': [],
        'GET /live/flows': [],
      }),
    )
    renderAppAt('/live')
    expect(await screen.findByText('No collectors registered')).toBeInTheDocument()
    expect(screen.getByText('No flows received yet')).toBeInTheDocument()
    expect(screen.getByText('None (needs an active full_no_ttl model)')).toBeInTheDocument()
  })

  it('shows an offline collector and its last reported problem', async () => {
    mockApi(
      liveRoutes({
        'GET /collectors': [
          { ...COLLECTOR, online: false, last_error: 'lab_00003.pcapng: tshark failed' },
        ],
      }),
    )
    renderAppAt('/live')
    expect(await screen.findByText('Offline')).toBeInTheDocument()
    expect(screen.getByText('lab_00003.pcapng: tshark failed')).toBeInTheDocument()
  })

  it('shows the server refusing inference while the gate is closed', async () => {
    const user = userEvent.setup()
    const api = mockApi(
      liveRoutes({
        'PATCH /collectors/1': apiError(409, 'live_gate_closed', CLOSED_GATE.reason),
      }),
      { user: ADMIN },
    )
    renderAppAt('/live')
    await user.click(await screen.findByRole('button', { name: 'Switch to inference…' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('the server will refuse this')
    await user.click(within(dialog).getByRole('button', { name: 'Start scoring' }))
    expect(await within(dialog).findByText(CLOSED_GATE.reason)).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/collectors/1')[0]?.body).toEqual({ mode: 'inference' })
  })

  it('refetches flows when a notification says new flows arrived', async () => {
    const api = mockApi(liveRoutes())
    renderAppAt('/live')
    await screen.findByRole('table', { name: 'Recent flows' })
    const before = api.callsTo('GET', '/live/flows').length
    act(() => {
      FakeWebSocket.latest().open()
      FakeWebSocket.latest().send({ type: 'flows.observed', count: 3 })
      FakeWebSocket.latest().send({ type: 'flows.observed', count: 2 })
    })
    expect(await screen.findByText('Live updates on')).toBeInTheDocument()
    // Both notifications are covered by one refetch.
    await waitFor(() => expect(api.callsTo('GET', '/live/flows')).toHaveLength(before + 1), {
      timeout: 3000,
    })
  })
})

describe('Dashboard live refresh', () => {
  it('refetches the summary when a live alert is created', async () => {
    const api = mockApi({
      'GET /dashboard/summary': EMPTY_DASHBOARD,
      'GET /health/components': COMPONENTS,
    })
    renderAppAt('/')
    await screen.findByText('No alerts yet')
    const before = api.callsTo('GET', '/dashboard/summary').length
    act(() => {
      FakeWebSocket.latest().open()
      FakeWebSocket.latest().send({ type: 'alert.created', alert: { id: 9 } })
    })
    await waitFor(() => expect(api.callsTo('GET', '/dashboard/summary')).toHaveLength(before + 1), {
      timeout: 3000,
    })
  })
})

function Probe({ onEvent }: { onEvent: () => void }) {
  const connected = useLiveConnection()
  useRefreshOn(['resync'], onEvent, 0)
  return <p>{connected ? 'connected' : 'disconnected'}</p>
}

describe('LiveEventsProvider', () => {
  it('builds the socket URL from the API base', () => {
    expect(eventsUrl('/api/v1', 'http://localhost:5173/live')).toBe(
      'ws://localhost:5173/api/v1/events',
    )
    expect(eventsUrl('https://sentinel.lab/api/v1', 'http://localhost:5173/')).toBe(
      'wss://sentinel.lab/api/v1/events',
    )
  })

  it('reconnects after the socket drops and asks pages to resync', async () => {
    let resyncs = 0
    render(
      <LiveEventsProvider>
        <Probe onEvent={() => (resyncs += 1)} />
      </LiveEventsProvider>,
    )
    const first = FakeWebSocket.latest()
    act(() => first.open())
    expect(screen.getByText('connected')).toBeInTheDocument()
    act(() => first.drop())
    expect(screen.getByText('disconnected')).toBeInTheDocument()
    // First retry after one second.
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2), { timeout: 2500 })
    act(() => FakeWebSocket.latest().open())
    await waitFor(() => expect(resyncs).toBe(1))
    // Malformed notifications are ignored rather than crashing the page.
    act(() => FakeWebSocket.latest().onmessage?.({ data: 'not json' }))
    expect(screen.getByText('connected')).toBeInTheDocument()
  })
})
