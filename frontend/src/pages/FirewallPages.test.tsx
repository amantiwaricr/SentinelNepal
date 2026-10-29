import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ADMIN, ADMIN_2, ANALYST, page, SYNTHETIC_FIREWALL_REQUEST } from '../test/fixtures'
import { apiError, mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'
import type { FirewallRequestOut } from '../types/api'

const DIRECTORY = [ADMIN, ANALYST, ADMIN_2]
const STATUS = {
  helper: 'not_configured',
  detail: 'The firewall helper is added in Phase 7.',
  protected_networks: ['127.0.0.0/8', '10.10.0.0/24'],
  max_duration_seconds: 3600,
  self_approval_allowed: false,
}

describe('Firewall approvals', () => {
  it('lists requests with requester, status, expiry, execution result and reversal', async () => {
    mockApi(
      {
        'GET /users/directory': DIRECTORY,
        'GET /firewall/status': STATUS,
        'GET /firewall/requests': page([
          SYNTHETIC_FIREWALL_REQUEST,
          {
            ...SYNTHETIC_FIREWALL_REQUEST,
            id: 10,
            target: '198.51.100.0/24',
            status: 'revoked',
            approved_by: 1,
            approved_at: '2026-10-28T12:05:00Z',
            revoked_by: 1,
            revoked_at: '2026-10-28T12:10:00Z',
          },
        ]),
      },
      { user: ADMIN },
    )
    renderAppAt('/firewall')
    const table = await screen.findByRole('table', { name: 'Firewall block requests' })
    const rows = within(table).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('192.0.2.10/32')
    expect(rows[1]).toHaveTextContent('admin2')
    expect(rows[1]).toHaveTextContent('Pending approval')
    expect(rows[1]).toHaveTextContent('No expiry (not applied)')
    expect(rows[1]).toHaveTextContent('Awaiting decision')
    expect(rows[2]).toHaveTextContent('Revoked by admin1')
    expect(rows[2]).toHaveTextContent('Not executed: no firewall helper')
    // Admins also see the helper configuration.
    expect(screen.getByText('127.0.0.0/8, 10.10.0.0/24')).toBeInTheDocument()
  })

  it('approves only after the admin types the exact target', async () => {
    const user = userEvent.setup()
    let request: FirewallRequestOut = { ...SYNTHETIC_FIREWALL_REQUEST }
    const api = mockApi(
      {
        'GET /users/directory': DIRECTORY,
        'GET /firewall/requests/9': () => request,
        'POST /firewall/requests/9/approve': () => {
          request = {
            ...request,
            status: 'approved',
            approved_by: 1,
            approved_at: '2026-10-28T12:30:00Z',
          }
          return request
        },
      },
      { user: ADMIN },
    )
    renderAppAt('/firewall/9')
    await user.click(await screen.findByRole('button', { name: 'Approve block…' }))
    const dialog = screen.getByRole('dialog', { name: 'Approve blocking 192.0.2.10/32?' })
    const approve = within(dialog).getByRole('button', { name: 'Approve block' })
    expect(approve).toBeDisabled()
    await user.type(within(dialog).getByLabelText(/to confirm/), '192.0.2.10/32')
    await user.click(approve)

    expect(await screen.findByText('Approved (not applied)')).toBeInTheDocument()
    expect(api.callsTo('POST', '/firewall/requests/9/approve')[0]?.body).toEqual({
      confirm_target: '192.0.2.10/32',
      note: null,
    })
    // Approval is a decision only: nothing claims the rule was applied.
    expect(
      screen.getByText('No firewall rule has been applied for this request.', { exact: false }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Not executed: no firewall helper (added in Phase 7)'),
    ).toBeInTheDocument()
  })

  it('shows the server refusal of self-approval', async () => {
    const user = userEvent.setup()
    mockApi(
      {
        'GET /users/directory': DIRECTORY,
        'GET /firewall/requests/9': { ...SYNTHETIC_FIREWALL_REQUEST, requested_by: ADMIN.id },
        'POST /firewall/requests/9/approve': apiError(
          403,
          'self_approval',
          'A different administrator must approve this request',
        ),
      },
      { user: ADMIN },
    )
    renderAppAt('/firewall/9')
    expect(await screen.findByText(/You made this request/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Approve block…' }))
    const dialog = screen.getByRole('dialog')
    await user.type(within(dialog).getByLabelText(/to confirm/), '192.0.2.10/32')
    await user.click(within(dialog).getByRole('button', { name: 'Approve block' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'A different administrator must approve this request',
    )
  })

  it('rejecting requires a reason', async () => {
    const user = userEvent.setup()
    let request: FirewallRequestOut = { ...SYNTHETIC_FIREWALL_REQUEST }
    const api = mockApi(
      {
        'GET /users/directory': DIRECTORY,
        'GET /firewall/requests/9': () => request,
        'POST /firewall/requests/9/reject': () => {
          request = { ...request, status: 'rejected' }
          return request
        },
      },
      { user: ADMIN },
    )
    renderAppAt('/firewall/9')
    await user.click(await screen.findByRole('button', { name: 'Reject…' }))
    const dialog = screen.getByRole('dialog')
    const reject = within(dialog).getByRole('button', { name: 'Reject' })
    expect(reject).toBeDisabled()
    await user.type(within(dialog).getByLabelText(/Reason for rejecting/), 'Evidence is too weak')
    await user.click(reject)
    await screen.findByText('Not executed (rejected)')
    expect(api.callsTo('POST', '/firewall/requests/9/reject')[0]?.body).toEqual({
      note: 'Evidence is too weak',
    })
  })

  it('does not offer approval to analysts', async () => {
    mockApi({
      'GET /users/directory': DIRECTORY,
      'GET /firewall/requests/9': SYNTHETIC_FIREWALL_REQUEST,
    })
    renderAppAt('/firewall/9')
    expect(
      await screen.findByText('An administrator must review and approve this request.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve block…' })).not.toBeInTheDocument()
  })

  it('creates a request prefilled from an alert', async () => {
    const user = userEvent.setup()
    const api = mockApi(
      {
        'GET /users/directory': DIRECTORY,
        'POST /firewall/requests': SYNTHETIC_FIREWALL_REQUEST,
        'GET /firewall/requests/9': SYNTHETIC_FIREWALL_REQUEST,
      },
      { user: ADMIN },
    )
    renderAppAt('/firewall/new?target=192.0.2.10&alert_id=7')
    expect(await screen.findByLabelText(/Target IP or CIDR/)).toHaveValue('192.0.2.10')
    const submit = screen.getByRole('button', { name: 'Submit for approval' })
    expect(submit).toBeDisabled()
    await user.type(screen.getByLabelText(/^Reason/), 'Repeated exploit attempts seen in host logs')
    await user.click(submit)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Block request 9' }),
    ).toBeInTheDocument()
    expect(api.callsTo('POST', '/firewall/requests')[0]?.body).toEqual({
      target: '192.0.2.10',
      duration_seconds: 900,
      reason: 'Repeated exploit attempts seen in host logs',
      alert_id: 7,
      incident_id: null,
      dry_run: false,
    })
  })
})
