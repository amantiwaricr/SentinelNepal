import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ADMIN, ANALYST, EMPTY_DASHBOARD, COMPONENTS, page } from './test/fixtures'
import { apiError, mockApi } from './test/mockApi'
import { renderAppAt } from './test/render'

describe('route guard and sign-in', () => {
  it('sends a signed-out visitor to the sign-in page, keeping where they were going', async () => {
    mockApi({}, { user: null })
    renderAppAt('/alerts?severity=high')
    expect(
      await screen.findByRole('heading', { name: 'Sign in to SentinelNepal' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument()
  })

  it('signs in and continues to the requested page', async () => {
    const user = userEvent.setup()
    let signedIn = false
    const api = mockApi(
      {
        'GET /auth/me': () => (signedIn ? ANALYST : apiError(401, 'unauthenticated', 'No')),
        'POST /auth/login': () => {
          signedIn = true
          return ANALYST
        },
        'GET /alerts': page([]),
      },
      { user: null },
    )
    renderAppAt('/alerts')
    await user.type(await screen.findByLabelText('Username'), 'analyst1')
    await user.type(screen.getByLabelText('Password'), 'a-long-password-1')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Alerts' })).toBeInTheDocument()
    expect(api.callsTo('POST', '/auth/login')[0]?.body).toEqual({
      username: 'analyst1',
      password: 'a-long-password-1',
    })
  })

  it('shows the server message when sign-in fails and clears the password', async () => {
    const user = userEvent.setup()
    mockApi(
      { 'POST /auth/login': apiError(401, 'invalid_credentials', 'Invalid username or password') },
      { user: null },
    )
    renderAppAt('/login')
    await user.type(await screen.findByLabelText('Username'), 'analyst1')
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password')
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('ignores an external "next" target after sign-in (no open redirect)', async () => {
    const user = userEvent.setup()
    let signedIn = false
    mockApi(
      {
        'GET /auth/me': () => (signedIn ? ANALYST : apiError(401, 'unauthenticated', 'No')),
        'POST /auth/login': () => {
          signedIn = true
          return ANALYST
        },
        'GET /dashboard/summary': EMPTY_DASHBOARD,
        'GET /health/components': COMPONENTS,
      },
      { user: null },
    )
    renderAppAt('/login?next=//evil.example/phish')
    await user.type(await screen.findByLabelText('Username'), 'analyst1')
    await user.type(screen.getByLabelText('Password'), 'a-long-password-1')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
  })

  it('returns to sign-in with an explanation when the session expires', async () => {
    const user = userEvent.setup()
    let expired = false
    mockApi({
      'GET /alerts': () =>
        expired ? apiError(401, 'unauthenticated', 'Session expired') : page([]),
      'GET /incidents': () => apiError(401, 'unauthenticated', 'Session expired'),
    })
    renderAppAt('/alerts')
    await screen.findByRole('heading', { level: 1, name: 'Alerts' })
    expired = true
    await user.click(screen.getByRole('link', { name: 'Incidents' }))
    expect(
      await screen.findByText('Your session has ended. Please sign in again.'),
    ).toBeInTheDocument()
  })

  it('signs out', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /alerts': page([]) })
    renderAppAt('/alerts')
    await user.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByText('You have signed out.')).toBeInTheDocument()
    expect(api.callsTo('POST', '/auth/logout')).toHaveLength(1)
  })

  it('hides admin pages from analysts and explains why', async () => {
    mockApi({})
    renderAppAt('/audit')
    expect(await screen.findByText('Not available for your role')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Audit Logs' })).not.toBeInTheDocument()
  })

  it('shows admin pages to admins', async () => {
    mockApi({ 'GET /audit-logs': page([]) }, { user: ADMIN })
    renderAppAt('/audit')
    expect(await screen.findByRole('heading', { level: 1, name: 'Audit Logs' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Audit Logs' })).toBeInTheDocument()
  })

  it('renders a not-found page for unknown routes', async () => {
    mockApi({})
    renderAppAt('/no/such/page')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Page not found' }),
    ).toBeInTheDocument()
  })
})
