import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { page, SYNTHETIC_ALERT_DETAIL, SYNTHETIC_INCIDENT } from '../test/fixtures'
import { mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'

const routes = {
  'GET /alerts/7': SYNTHETIC_ALERT_DETAIL,
  'GET /alerts': page([]),
}

describe('AlertDetailsPage', () => {
  it('presents the alert as a prediction with its evidence', async () => {
    mockApi(routes)
    renderAppAt('/alerts/7')
    expect(await screen.findByRole('heading', { level: 1, name: 'Alert 7' })).toBeInTheDocument()
    expect(screen.getByText('Model prediction, not proof')).toBeInTheDocument()
    expect(screen.getByText('Attack score (uncalibrated)')).toBeInTheDocument()
    expect(screen.getByText('0.815')).toBeInTheDocument()
    const scores = screen.getByRole('table', { name: 'Highest class scores from the model' })
    expect(within(scores).getByText('Generic')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '192.0.2.10:40000' })).toHaveAttribute(
      'href',
      '/ips?ip=192.0.2.10',
    )
    expect(screen.getByText(/The recommendation engine is added in\s+Phase 5/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Request block' })).toHaveAttribute(
      'href',
      '/firewall/new?target=192.0.2.10&alert_id=7',
    )
  })

  it('acknowledges the alert', async () => {
    const user = userEvent.setup()
    let status = 'new'
    const api = mockApi({
      ...routes,
      'GET /alerts/7': () => ({ ...SYNTHETIC_ALERT_DETAIL, status }),
      'PATCH /alerts/7': ({ body }) => {
        status = (body as { status: string }).status
        return { ...SYNTHETIC_ALERT_DETAIL, status }
      },
    })
    renderAppAt('/alerts/7')
    await user.click(await screen.findByRole('button', { name: 'Acknowledge' }))
    expect(await screen.findByRole('button', { name: 'Reopen' })).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/alerts/7')[0]?.body).toEqual({ status: 'acknowledged' })
  })

  it('opens an incident from the alert and goes to it', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      ...routes,
      'POST /incidents': SYNTHETIC_INCIDENT,
      'GET /incidents/4': SYNTHETIC_INCIDENT,
      'GET /incidents/4/notes': [],
      'GET /incidents/4/history': [],
    })
    renderAppAt('/alerts/7')
    await user.click(await screen.findByRole('button', { name: 'New incident' }))
    const dialog = screen.getByRole('dialog', { name: 'Open an investigation' })
    expect(within(dialog).getByLabelText(/^Title/)).toHaveValue(
      'Suspected Exploits from 192.0.2.10',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Create incident' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: /Incident 4: Suspected Exploits/ }),
    ).toBeInTheDocument()
    expect(api.callsTo('POST', '/incidents')[0]?.body).toEqual({
      title: 'Suspected Exploits from 192.0.2.10',
      severity: 'high',
      description: '',
      alert_ids: [7],
    })
  })
})
