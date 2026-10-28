import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderAppAt } from '../test/render'
import { NAV_ITEMS } from './navigation'

describe('AppLayout', () => {
  it('renders every primary navigation link', () => {
    renderAppAt('/')
    const nav = screen.getByRole('navigation', { name: 'Primary' })
    for (const item of NAV_ITEMS) {
      expect(within(nav).getByRole('link', { name: item.label })).toHaveAttribute('href', item.to)
    }
  })

  it('marks only the current page as active', () => {
    renderAppAt('/incidents')
    const nav = screen.getByRole('navigation', { name: 'Primary' })
    expect(within(nav).getByRole('link', { name: 'Incidents' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current')
  })

  it('navigates between pages through the sidebar', async () => {
    const user = userEvent.setup()
    renderAppAt('/')
    expect(screen.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()

    const nav = screen.getByRole('navigation', { name: 'Primary' })
    await user.click(within(nav).getByRole('link', { name: 'Alerts' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Alerts' })).toBeInTheDocument()
  })

  it('toggles the mobile navigation button state', async () => {
    const user = userEvent.setup()
    renderAppAt('/')
    const openButton = screen.getByRole('button', { name: 'Open navigation' })
    expect(openButton).toHaveAttribute('aria-expanded', 'false')
    await user.click(openButton)
    expect(openButton).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('button', { name: 'Close navigation' }))
    expect(openButton).toHaveAttribute('aria-expanded', 'false')
  })
})
