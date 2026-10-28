import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderAppAt } from './test/render'

describe('routing', () => {
  it.each([
    ['/alerts', 'Alerts'],
    ['/ips', 'IP Investigation'],
    ['/incidents', 'Incidents'],
    ['/recommendations', 'Recommendations'],
    ['/firewall', 'Firewall Approvals'],
    ['/audit', 'Audit Logs'],
    ['/model', 'Model Evaluation'],
  ])('%s renders the %s page as an honest placeholder', (path, title) => {
    renderAppAt(path)
    expect(screen.getByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(screen.getByText(/Not implemented yet/)).toBeInTheDocument()
  })

  it('shows the alert id on the alert details route', () => {
    renderAppAt('/alerts/42')
    expect(screen.getByRole('heading', { level: 1, name: 'Alert 42' })).toBeInTheDocument()
  })

  it('renders the login page outside the application layout', () => {
    renderAppAt('/login')
    expect(screen.getByRole('heading', { name: 'Sign in to SentinelNepal' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument()
  })

  it('renders a not-found page for unknown routes', () => {
    renderAppAt('/no/such/page')
    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeInTheDocument()
  })
})
