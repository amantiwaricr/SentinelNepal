import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import {
  ADMIN,
  ANALYST,
  COMPONENTS,
  page,
  SYNTHETIC_ALERT,
  SYNTHETIC_INCIDENT,
} from '../test/fixtures'
import { apiError, mockApi, respond } from '../test/mockApi'
import { renderAppAt } from '../test/render'
import type { AnalysisRunOut, IpSummaryOut, ModelVersionOut } from '../types/api'

const IP_SUMMARY: IpSummaryOut = {
  ip: '192.0.2.10',
  version: 4,
  alerts_total: 3,
  alerts_as_source: 3,
  alerts_as_destination: 0,
  first_seen: '2026-10-27T10:00:00Z',
  last_seen: '2026-10-28T10:00:00Z',
  by_category: { Exploits: 3 },
  by_severity: { high: 3 },
  destination_ports: { '80': 3 },
  protocols: { tcp: 3 },
  containing_subnet: '192.0.2.0/24',
  alerts_in_subnet: 5,
  recent_alerts: [SYNTHETIC_ALERT],
  note: 'Only alerts stored by SentinelNepal are shown. No geolocation or threat-intelligence lookups are performed.',
}

describe('IP investigation', () => {
  it('summarises stored alerts for an address without external enrichment', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'GET /ips/:ip': IP_SUMMARY })
    renderAppAt('/ips')
    await user.type(await screen.findByLabelText('IP address'), '192.0.2.10')
    await user.click(screen.getByRole('button', { name: 'Investigate address' }))
    expect(await screen.findByText('Address 192.0.2.10')).toBeInTheDocument()
    expect(screen.getByText(/No geolocation or threat-intelligence lookups/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '192.0.2.0/24' })).toHaveAttribute(
      'href',
      '/ips?cidr=192.0.2.0%2F24',
    )
    expect(
      screen.getByRole('table', { name: 'Recent alerts involving 192.0.2.10' }),
    ).toBeInTheDocument()
    expect(api.calls.at(-1)?.params).toEqual({ ip: '192.0.2.10' })
  })

  it('reports an invalid address from the API', async () => {
    mockApi({ 'GET /ips/:ip': apiError(422, 'invalid_ip', 'Not a valid IP address') })
    renderAppAt('/ips?ip=not-an-ip')
    expect(await screen.findByRole('alert')).toHaveTextContent('Not a valid IP address')
  })
})

describe('Incidents list', () => {
  it('filters by assignee and creates an incident', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /incidents': page([SYNTHETIC_INCIDENT]),
      'POST /incidents': SYNTHETIC_INCIDENT,
      'GET /incidents/4': SYNTHETIC_INCIDENT,
      'GET /incidents/4/notes': [],
      'GET /incidents/4/history': [],
    })
    renderAppAt('/incidents')
    expect(await screen.findByRole('link', { name: /#4 Suspected Exploits/ })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Assigned to'), 'Me (analyst1)')
    await screen.findByRole('link', { name: /#4 Suspected Exploits/ })
    expect(api.callsTo('GET', '/incidents').at(-1)?.query.get('assigned_to')).toBe(
      String(ANALYST.id),
    )

    await user.click(screen.getByRole('button', { name: 'New incident' }))
    const dialog = screen.getByRole('dialog', { name: 'New incident' })
    await user.type(within(dialog).getByLabelText(/^Title/), 'Port scan review')
    await user.click(within(dialog).getByRole('button', { name: 'Create incident' }))
    await screen.findByRole('heading', { level: 1, name: /Incident 4/ })
    expect(api.callsTo('POST', '/incidents')[0]?.body).toEqual({
      title: 'Port scan review',
      severity: 'medium',
      description: '',
      assigned_to: null,
    })
  })
})

const RUN: AnalysisRunOut = {
  id: 3,
  uploaded_by: 2,
  original_filename: 'synthetic.csv',
  file_sha256: 'a'.repeat(64),
  size_bytes: 2048,
  status: 'queued',
  detected_schema: null,
  model_version_id: 1,
  rows_total: 0,
  rows_valid: 0,
  rows_rejected: 0,
  alerts_created: 0,
  summary: {},
  error_message: null,
  created_at: '2026-10-28T10:00:00Z',
  started_at: null,
  finished_at: null,
}

describe('Dataset analysis', () => {
  it('uploads a CSV as multipart form data and lists the run', async () => {
    const user = userEvent.setup()
    const runs: AnalysisRunOut[] = []
    const api = mockApi({
      'GET /datasets/analyses': () => page(runs),
      'POST /datasets/analyses': () => {
        runs.push(RUN)
        return respond(202, RUN)
      },
    })
    renderAppAt('/datasets')
    expect(await screen.findByText('No files analysed yet')).toBeInTheDocument()
    const file = new File(['dur,proto\n0.1,tcp\n'], 'synthetic.csv', { type: 'text/csv' })
    await user.upload(screen.getByLabelText('UNSW-NB15 CSV file'), file)
    await user.click(screen.getByRole('button', { name: 'Upload and analyse' }))
    expect(await screen.findByText('#3 synthetic.csv')).toBeInTheDocument()
    expect(screen.getByText('Queued')).toBeInTheDocument()
    const body = api.callsTo('POST', '/datasets/analyses')[0]?.body
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('file')).toBeInstanceOf(File)
  })

  it('links a completed run to its alerts and shows rejection reasons', async () => {
    mockApi({
      'GET /datasets/analyses': page([
        {
          ...RUN,
          status: 'completed',
          rows_total: 400,
          rows_valid: 395,
          rows_rejected: 5,
          alerts_created: 261,
          summary: { rejection_reasons: { 'sbytes: not a number': 5 } },
        },
      ]),
    })
    renderAppAt('/datasets')
    expect(await screen.findByRole('link', { name: '261 alerts' })).toHaveAttribute(
      'href',
      '/alerts?run_id=3',
    )
    expect(screen.getByText('400 (395 / 5)')).toBeInTheDocument()
    expect(screen.getByText('sbytes: not a number')).toBeInTheDocument()
  })
})

const MODEL: ModelVersionOut = {
  id: 1,
  name: 'random_forest',
  version: 'synthetic',
  model_kind: 'random_forest_balanced',
  feature_profile: 'full',
  artifact_sha256: 'b'.repeat(64),
  features: ['dur', 'proto'],
  class_labels: ['Normal', 'DoS', 'Exploits'],
  metrics: {
    validation: {
      macro_f1: 0.6,
      attack_recall: 0.99,
      false_positive_rate: 0.17,
      per_class_precision: { Normal: 0.99, DoS: 0.3, Exploits: 0.7 },
    },
  },
  alert_threshold: 0.815,
  threshold_details: {
    target_fpr: 0.05,
    selected_on: 'validation split of the training file (testing file not used)',
    chosen: {
      threshold: 0.815,
      false_positive_rate: 0.0492,
      attack_recall: 0.9025,
      share_alerted: 0.49,
    },
  },
  is_active: false,
  live_inference_approved: false,
  low_precision_categories: ['DoS'],
  precision_source: 'validation',
  activated_at: null,
  created_at: '2026-10-28T10:00:00Z',
}

describe('Model evaluation', () => {
  it('shows recorded metrics, the threshold and unreliable categories', async () => {
    mockApi({ 'GET /models': [MODEL] })
    renderAppAt('/model')
    expect(await screen.findByText('random_forest synthetic')).toBeInTheDocument()
    expect(screen.getByText('Dataset results, not live performance')).toBeInTheDocument()
    expect(screen.getByText('FPR 4.9%, attack recall 90.3%')).toBeInTheDocument()
    const precision = screen.getByRole('table', {
      name: 'Precision per class on the validation data',
    })
    const dosRow = within(precision).getByText('DoS').closest('tr')
    expect(dosRow).toHaveTextContent('Unreliable label')
    expect(within(precision).getByText('Exploits').closest('tr')).not.toHaveTextContent(
      'Unreliable',
    )
    // Analysts cannot activate or approve models.
    expect(screen.queryByRole('button', { name: 'Activate…' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve for live use…' })).not.toBeInTheDocument()
  })

  it('lets an admin activate a model after confirming', async () => {
    const user = userEvent.setup()
    let active = false
    const api = mockApi(
      {
        'GET /models': () => [{ ...MODEL, is_active: active }],
        'POST /models/1/activate': () => {
          active = true
          return { ...MODEL, is_active: true }
        },
      },
      { user: ADMIN },
    )
    renderAppAt('/model')
    await user.click(await screen.findByRole('button', { name: 'Activate…' }))
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Activate model' }),
    )
    expect(await screen.findByText('Active')).toBeInTheDocument()
    expect(api.callsTo('POST', '/models/1/activate')).toHaveLength(1)
  })

  it('shows the server refusing live approval for an incompatible model', async () => {
    const user = userEvent.setup()
    const api = mockApi(
      {
        'GET /models': [MODEL],
        'POST /models/1/live-approval': apiError(
          409,
          'incompatible_model',
          'Live traffic cannot supply: ct_state_ttl',
        ),
      },
      { user: ADMIN },
    )
    renderAppAt('/model')
    await user.click(await screen.findByRole('button', { name: 'Approve for live use…' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('uncalibrated suspicions')
    await user.click(within(dialog).getByRole('button', { name: 'Approve' }))
    expect(await within(dialog).findByText(/ct_state_ttl/)).toBeInTheDocument()
    expect(api.callsTo('POST', '/models/1/live-approval')[0]?.body).toEqual({ approved: true })
  })
})

describe('System & Settings', () => {
  const READY = {
    status: 'ready',
    service: 'SentinelNepal',
    version: '0.1.0',
    environment: 'development',
    components: {
      database: { status: 'ok', detail: null },
      migrations: { status: 'ok', detail: 'At head' },
    },
  }

  it('treats a 503 readiness response as data', async () => {
    mockApi({
      'GET /health/ready': respond(503, { ...READY, status: 'not_ready' }),
      'GET /health/components': COMPONENTS,
    })
    renderAppAt('/system')
    expect(await screen.findByText('Not ready')).toBeInTheDocument()
    expect(screen.getByText('At head')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('lets an admin create a user and shows password rules from the server', async () => {
    const user = userEvent.setup()
    const api = mockApi(
      {
        'GET /health/ready': READY,
        'GET /health/components': COMPONENTS,
        'GET /users': page([ADMIN]),
        'POST /users': ({ body }) =>
          (body as { password: string }).password.length < 12
            ? apiError(422, 'weak_password', 'Password must be at least 12 characters')
            : { ...ANALYST, id: 9, username: 'sita' },
      },
      { user: ADMIN },
    )
    renderAppAt('/system')
    await user.click(await screen.findByRole('button', { name: 'Add user' }))
    const dialog = screen.getByRole('dialog', { name: 'Add user' })
    await user.type(within(dialog).getByLabelText(/^Username/), 'sita')
    await user.type(within(dialog).getByLabelText(/^Initial password/), 'short')
    await user.click(within(dialog).getByRole('button', { name: 'Create user' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('at least 12 characters')

    await user.clear(within(dialog).getByLabelText(/^Initial password/))
    await user.type(within(dialog).getByLabelText(/^Initial password/), 'a-long-enough-pass')
    await user.click(within(dialog).getByRole('button', { name: 'Create user' }))
    await screen.findByRole('button', { name: 'Add user' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(api.callsTo('POST', '/users').at(-1)?.body).toEqual({
      username: 'sita',
      password: 'a-long-enough-pass',
      role: 'analyst',
    })
  })
})

describe('Audit logs', () => {
  it('filters by action and outcome and shows details as text', async () => {
    const user = userEvent.setup()
    const api = mockApi(
      {
        'GET /audit-logs': page([
          {
            id: 1,
            occurred_at: '2026-10-28T10:00:00Z',
            actor_type: 'anonymous',
            actor_user_id: null,
            actor_label: 'mallory',
            action: 'auth.login',
            target_type: null,
            target_id: null,
            outcome: 'failure',
            ip_address: '192.0.2.50',
            request_id: 'abcdef123456',
            details: { reason: '<script>bad()</script>' },
          },
        ]),
      },
      { user: ADMIN },
    )
    renderAppAt('/audit')
    expect(await screen.findByText('{"reason":"<script>bad()</script>"}')).toBeInTheDocument()
    expect(document.querySelector('main script')).toBeNull()
    await user.type(screen.getByLabelText('Action'), 'auth.login')
    await user.selectOptions(screen.getByLabelText('Outcome'), 'failure')
    await user.click(screen.getByRole('button', { name: 'Apply filters' }))
    await screen.findByRole('button', { name: 'Clear' })
    const query = api.callsTo('GET', '/audit-logs').at(-1)?.query
    expect(query?.get('action')).toBe('auth.login')
    expect(query?.get('outcome')).toBe('failure')
  })
})
