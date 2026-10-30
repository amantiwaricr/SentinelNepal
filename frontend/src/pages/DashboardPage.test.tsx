import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { COMPONENTS, EMPTY_DASHBOARD } from '../test/fixtures'
import { mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'
import type { DashboardOut } from '../types/api'

const SYNTHETIC_DASHBOARD: DashboardOut = {
  ...EMPTY_DASHBOARD,
  alerts_total: 1234,
  alerts_new: 56,
  alerts_by_severity: { high: 1000, critical: 234 },
  alerts_by_category: { Exploits: 1000, DoS: 234 },
  alerts_by_status: { new: 56, acknowledged: 1178 },
  alerts_by_source: { dataset: 1234 },
  alert_activity_by_day: [{ day: '2026-10-28T00:00:00Z', count: 1234 }],
  top_source_ips: { '192.0.2.10': 800 },
  incidents_by_status: { new: 2, under_investigation: 1, resolved: 4 },
  analysis_runs_by_status: { completed: 1 },
  active_models: [
    {
      id: 1,
      feature_profile: 'full',
      name: 'random_forest',
      version: 'synthetic',
      alert_threshold: 0.815,
    },
  ],
}

/** The number shown on a stat card, found by the card's label. */
function statValue(label: string): string | null | undefined {
  return screen.getByText(label).parentElement?.nextElementSibling?.textContent
}

describe('DashboardPage', () => {
  it('shows figures from the API, not built-in numbers', async () => {
    mockApi({ 'GET /dashboard/summary': SYNTHETIC_DASHBOARD, 'GET /health/components': COMPONENTS })
    renderAppAt('/')
    await screen.findByText('Total alerts')
    expect(statValue('Total alerts')).toBe('1,234')
    expect(statValue('New (unreviewed) alerts')).toBe('56')
    expect(statValue('Open incidents')).toBe('3') // new + under investigation
    expect(statValue('Active model')).toContain('random_forest')
    expect(screen.getByText('full · threshold 0.815')).toBeInTheDocument()
    const ips = screen.getByRole('table', { name: 'Most frequent source IP addresses' })
    expect(within(ips).getByRole('link', { name: '192.0.2.10' })).toHaveAttribute(
      'href',
      '/ips?ip=192.0.2.10',
    )
    expect(await screen.findByText('Dataset-analysis model')).toBeInTheDocument()
    expect(screen.getByText('No collectors registered')).toBeInTheDocument()
  })

  it('shows empty states on a fresh database', async () => {
    mockApi({ 'GET /dashboard/summary': EMPTY_DASHBOARD, 'GET /health/components': COMPONENTS })
    renderAppAt('/')
    expect(await screen.findByText('No alerts yet')).toBeInTheDocument()
    expect(screen.getByText('No incidents yet')).toBeInTheDocument()
    expect(screen.getByText('No alerts to categorise')).toBeInTheDocument()
    expect(screen.getByText('Register and activate a model for this view')).toBeInTheDocument()
  })

  it('switches between all, dataset and live data and labels them', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /dashboard/summary': ({ query }) => ({
        ...EMPTY_DASHBOARD,
        source: query.get('source') ?? 'all',
      }),
      'GET /health/components': COMPONENTS,
    })
    renderAppAt('/')
    await screen.findByText('No alerts yet')
    await user.click(screen.getByRole('radio', { name: 'Dataset analysis' }))
    expect(await screen.findByText('Dataset-analysis results')).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Live & replay' }))
    expect(
      await screen.findByText(
        'No live or replayed alerts exist. Live Monitoring shows collector status and the score of each recent flow.',
      ),
    ).toBeInTheDocument()
    expect(api.callsTo('GET', '/dashboard/summary').map((c) => c.query.get('source'))).toEqual([
      'all',
      'dataset',
      'live',
    ])
  })
})
