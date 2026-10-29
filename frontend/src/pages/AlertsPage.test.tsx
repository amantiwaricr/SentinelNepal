import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { page, SYNTHETIC_ALERT } from '../test/fixtures'
import { mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'

describe('AlertsPage', () => {
  it('lists alerts with their source tag, score and links to investigations', async () => {
    mockApi({ 'GET /alerts': page([SYNTHETIC_ALERT]) })
    renderAppAt('/alerts')
    const table = await screen.findByRole('table', { name: 'Alerts matching the filters' })
    expect(within(table).getByRole('link', { name: '#7' })).toHaveAttribute('href', '/alerts/7')
    expect(within(table).getByRole('link', { name: '192.0.2.10:40000' })).toHaveAttribute(
      'href',
      '/ips?ip=192.0.2.10',
    )
    expect(within(table).getByText('Dataset')).toBeInTheDocument()
    expect(within(table).getByText('0.930')).toBeInTheDocument()
    expect(within(table).getByText('Exploits')).toBeInTheDocument()
  })

  it('sends filters to the API and keeps them in the URL', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /alerts': page([]) })
    renderAppAt('/alerts')
    await screen.findByText('No alerts yet')

    await user.type(screen.getByLabelText('Source IP'), '192.0.2.10')
    await user.selectOptions(screen.getByLabelText('Severity'), 'high')
    await user.selectOptions(screen.getByLabelText('Suspected category'), 'DoS')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))

    await screen.findByText('No alerts match these filters')
    const last = api.callsTo('GET', '/alerts').at(-1)
    expect(Object.fromEntries(last?.query ?? [])).toEqual({
      src_ip: '192.0.2.10',
      severity: 'high',
      category: 'DoS',
      sort: '-created_at',
      page: '1',
      page_size: '25',
    })
    // The form shows the applied filters, and Clear resets them.
    expect(screen.getByLabelText('Source IP')).toHaveValue('192.0.2.10')
    await user.click(screen.getByRole('button', { name: 'Clear' }))
    await screen.findByText('No alerts yet')
    expect(screen.getByLabelText('Source IP')).toHaveValue('')
  })

  it('reads filters from the URL and ignores invalid values', async () => {
    const api = mockApi({ 'GET /alerts': page([]) })
    renderAppAt('/alerts?status=new&severity=bogus&run_id=3')
    await screen.findByText('Showing alerts from analysis run #3')
    const query = Object.fromEntries(api.callsTo('GET', '/alerts')[0]?.query ?? [])
    expect(query).toMatchObject({ status: 'new', run_id: '3' })
    expect(query).not.toHaveProperty('severity')
  })

  it('pages and sorts results', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /alerts': ({ query }) => page([SYNTHETIC_ALERT], 60, Number(query.get('page') ?? 1), 25),
    })
    renderAppAt('/alerts')
    await screen.findByText('Showing 1–25 of 60')
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText('Showing 26–50 of 60')
    await user.selectOptions(screen.getByLabelText('Sort'), '-attack_score')
    await screen.findByText('Showing 1–25 of 60')
    const query = api.callsTo('GET', '/alerts').at(-1)?.query
    expect(query?.get('sort')).toBe('-attack_score')
    expect(query?.get('page')).toBe('1')
  })

  it('shows a retryable error', async () => {
    const user = userEvent.setup()
    let fail = true
    mockApi({
      'GET /alerts': () => {
        if (fail) throw new TypeError('network down')
        return page([])
      },
    })
    renderAppAt('/alerts')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not reach the SentinelNepal API',
    )
    fail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No alerts yet')).toBeInTheDocument()
  })
})
