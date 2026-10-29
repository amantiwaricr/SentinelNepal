import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ADMIN, EMPTY_DASHBOARD, COMPONENTS, page } from '../test/fixtures'
import { mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'
import { NAV_ITEMS, navItemsFor } from './navigation'

const BASE = { 'GET /dashboard/summary': EMPTY_DASHBOARD, 'GET /health/components': COMPONENTS }

describe('AppLayout', () => {
  it('shows every navigation link to an admin', async () => {
    mockApi(BASE, { user: ADMIN })
    renderAppAt('/')
    const nav = await screen.findByRole('navigation', { name: 'Primary' })
    for (const item of NAV_ITEMS) {
      expect(within(nav).getByRole('link', { name: item.label })).toHaveAttribute('href', item.to)
    }
  })

  it('omits admin-only links for analysts', () => {
    expect(navItemsFor('analyst').map((i) => i.label)).not.toContain('Audit Logs')
    expect(navItemsFor('admin').map((i) => i.label)).toContain('Audit Logs')
  })

  it('shows who is signed in', async () => {
    mockApi(BASE, { user: ADMIN })
    renderAppAt('/')
    const banner = await screen.findByRole('banner')
    expect(within(banner).getByText('admin1')).toBeInTheDocument()
    expect(within(banner).getByText('admin')).toBeInTheDocument()
  })

  it('marks only the current page as active and navigates', async () => {
    const user = userEvent.setup()
    mockApi({ ...BASE, 'GET /alerts': page([]) })
    renderAppAt('/')
    const nav = await screen.findByRole('navigation', { name: 'Primary' })
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await user.click(within(nav).getByRole('link', { name: 'Alerts' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Alerts' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current')
  })

  it('toggles the mobile navigation button state', async () => {
    const user = userEvent.setup()
    mockApi(BASE)
    renderAppAt('/')
    const openButton = await screen.findByRole('button', { name: 'Open navigation' })
    expect(openButton).toHaveAttribute('aria-expanded', 'false')
    await user.click(openButton)
    expect(openButton).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('button', { name: 'Close navigation' }))
    expect(openButton).toHaveAttribute('aria-expanded', 'false')
  })
})
