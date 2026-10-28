import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { mockFetchJson } from '../test/helpers'
import { renderAppAt } from '../test/render'

const READY = {
  status: 'ready',
  service: 'SentinelNepal',
  version: '0.1.0',
  environment: 'development',
  components: {
    database: { status: 'ok', detail: null },
    migrations: { status: 'ok', detail: 'At revision 0001' },
  },
}

const NOT_READY = {
  ...READY,
  status: 'not_ready',
  components: {
    database: { status: 'ok', detail: null },
    migrations: { status: 'pending', detail: "No migrations applied; run 'alembic upgrade head'" },
  },
}

describe('SystemHealthPage', () => {
  it('shows a ready backend with component details', async () => {
    const fetchMock = mockFetchJson(200, READY)
    renderAppAt('/system')

    expect(await screen.findByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Database migrations')).toBeInTheDocument()
    expect(screen.getByText('At revision 0001')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health/ready', expect.anything())
  })

  it('treats a 503 readiness response as data and shows what is not ready', async () => {
    mockFetchJson(503, NOT_READY)
    renderAppAt('/system')

    expect(await screen.findByText('Not ready')).toBeInTheDocument()
    expect(screen.getByText('pending')).toBeInTheDocument()
    expect(screen.getByText(/run 'alembic upgrade head'/)).toBeInTheDocument()
  })

  it('shows an error with the request id when the API returns an error envelope', async () => {
    mockFetchJson(500, {
      error: {
        code: 'internal_error',
        message: 'An unexpected error occurred',
        details: null,
        request_id: 'req-1234',
      },
    })
    renderAppAt('/system')

    expect(await screen.findByRole('alert')).toHaveTextContent('An unexpected error occurred')
    expect(screen.getByText('Request ID: req-1234')).toBeInTheDocument()
  })

  it('shows a retryable error when the API cannot be reached', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch'))
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(READY), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAppAt('/system')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not reach the SentinelNepal API',
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Ready')).toBeInTheDocument()
  })
})
