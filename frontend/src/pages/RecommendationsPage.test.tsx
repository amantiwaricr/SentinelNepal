import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'
import type { RuleOut } from '../types/api'

const RULES: RuleOut[] = [
  {
    rule_id: 'exploit.contain',
    version: '1',
    group: 'exploit',
    categories: ['Backdoor', 'Exploits'],
    kind: 'contain',
    heuristic: false,
    action: 'Consider requesting a temporary block of {src}.',
    reason: 'Synthetic reason.',
    required_evidence: [
      { name: 'source_address', description: 'The source IP address is recorded' },
    ],
    priority: 'high',
    limitations: 'Synthetic limitation.',
    requires_human_approval: true,
  },
  {
    rule_id: 'bruteforce_like.review_auth',
    version: '1',
    group: 'bruteforce_like',
    categories: [],
    kind: 'harden',
    heuristic: true,
    action: 'Review authentication logs.',
    reason: 'Heuristic, not a model prediction.',
    required_evidence: [],
    priority: 'medium',
    limitations: 'Synthetic limitation.',
    requires_human_approval: true,
  },
]

describe('RecommendationsPage', () => {
  it('lists the rule catalogue with evidence, kinds and approval needs', async () => {
    mockApi({ 'GET /recommendations/rules': RULES })
    renderAppAt('/recommendations')
    const contain = (await screen.findByText('exploit.contain')).closest('section')!
    expect(within(contain).getByText('Contain')).toBeInTheDocument()
    expect(within(contain).getByText('Needs approval')).toBeInTheDocument()
    expect(
      within(contain).getByText('Consider requesting a temporary block of ‹src›.'),
    ).toBeInTheDocument()
    expect(within(contain).getByText('The source IP address is recorded')).toBeInTheDocument()
    expect(within(contain).getByText(/applies to: Backdoor, Exploits/)).toBeInTheDocument()
    const heuristic = screen.getByText('bruteforce_like.review_auth').closest('section')!
    expect(within(heuristic).getByText(/Heuristic over stored alerts/)).toBeInTheDocument()
    expect(screen.getByText('Suggestions, not verdicts')).toBeInTheDocument()
  })
})
