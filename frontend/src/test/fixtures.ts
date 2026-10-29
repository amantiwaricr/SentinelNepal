/**
 * Synthetic API responses for component tests. They are hand-written examples shaped like
 * the backend's schemas, not real alerts, traffic or model results.
 */
import type {
  AlertDetail,
  AlertOut,
  DashboardOut,
  FirewallRequestOut,
  IncidentDetail,
  Page,
  UserOut,
} from '../types/api'

export const ANALYST: UserOut = {
  id: 2,
  username: 'analyst1',
  role: 'analyst',
  is_active: true,
  last_login_at: null,
  created_at: '2026-10-01T00:00:00Z',
}

export const ADMIN: UserOut = { ...ANALYST, id: 1, username: 'admin1', role: 'admin' }
export const ADMIN_2: UserOut = { ...ANALYST, id: 3, username: 'admin2', role: 'admin' }

export function page<T>(items: T[], total = items.length, pageNumber = 1, pageSize = 25): Page<T> {
  return { items, total, page: pageNumber, page_size: pageSize }
}

export const SYNTHETIC_ALERT: AlertOut = {
  id: 7,
  source: 'dataset',
  analysis_run_id: 3,
  model_version_id: 1,
  observed_at: null,
  src_ip: '192.0.2.10',
  dst_ip: '198.51.100.20',
  src_port: 40000,
  dst_port: 80,
  protocol: 'tcp',
  service: 'http',
  predicted_category: 'Exploits',
  attack_score: 0.93,
  severity: 'high',
  status: 'new',
  created_at: '2026-10-28T10:00:00Z',
}

export const SYNTHETIC_ALERT_DETAIL: AlertDetail = {
  ...SYNTHETIC_ALERT,
  evidence: {
    class_scores_top3: { Exploits: 0.61, Generic: 0.2, Normal: 0.07 },
    default_decision: 'Exploits',
    alert_threshold: 0.815,
    features: { dur: 0.12, proto: 'tcp', sbytes: 1024 },
    imputed_features: [],
    unknown_categories: {},
    severity_rule: 'synthetic rule text',
    note: 'Model scores are uncalibrated; this alert is a prediction, not proof.',
  },
  model: { id: 1, name: 'random_forest', version: 'synthetic', feature_profile: 'full' },
  recommendations: [
    {
      id: 1,
      alert_id: 7,
      rule_id: 'exploit.inspect_target',
      rule_version: '1',
      category: 'Exploits',
      action: 'Inspect the targeted service at 198.51.100.20:80.',
      reason: 'Synthetic reason text.',
      required_evidence: ['destination_address'],
      evidence_present: {
        destination_address: {
          met: true,
          description: 'The destination IP address is recorded',
          observed: '198.51.100.20',
        },
      },
      priority: 'high',
      limitations: 'Synthetic limitation: the alert is not proof.',
      requires_human_approval: false,
      created_at: '2026-10-28T10:05:00Z',
    },
    {
      id: 2,
      alert_id: 7,
      rule_id: 'fallback.investigate',
      rule_version: '1',
      category: 'Exploits',
      action: 'Investigate further before considering stronger action.',
      reason:
        'Stronger actions were not suggested because evidence is missing: exploit.contain (missing: reliable_category).',
      required_evidence: ['reliable_category'],
      evidence_present: {
        reliable_category: {
          met: false,
          description: "The model's recorded precision for this category is at least 50%",
          observed: '20.0% on the test data',
        },
      },
      priority: 'low',
      limitations: 'Synthetic limitation.',
      requires_human_approval: false,
      created_at: '2026-10-28T10:05:00Z',
    },
  ],
  incidents: [],
}

export const SYNTHETIC_INCIDENT: IncidentDetail = {
  id: 4,
  title: 'Suspected Exploits from 192.0.2.10',
  description: 'Synthetic incident for tests.',
  status: 'new',
  severity: 'high',
  created_by: 2,
  assigned_to: null,
  resolved_at: null,
  created_at: '2026-10-28T11:00:00Z',
  updated_at: '2026-10-28T11:00:00Z',
  alert_count: 1,
  alerts: [{ ...SYNTHETIC_ALERT, status: 'linked' }],
  allowed_transitions: ['under_investigation', 'false_positive'],
}

export const SYNTHETIC_FIREWALL_REQUEST: FirewallRequestOut = {
  id: 9,
  target: '192.0.2.10/32',
  ip_version: 4,
  reason: 'Synthetic test request with enough words',
  alert_id: 7,
  incident_id: null,
  requested_by: 3,
  status: 'pending',
  duration_seconds: 900,
  dry_run: false,
  approved_by: null,
  approved_at: null,
  decision_note: null,
  applied_at: null,
  expires_at: null,
  revoked_by: null,
  revoked_at: null,
  created_at: '2026-10-28T12:00:00Z',
  results: [],
  applied: false,
}

export const EMPTY_DASHBOARD: DashboardOut = {
  source: 'all',
  generated_at: '2026-10-28T12:00:00Z',
  alerts_total: 0,
  alerts_new: 0,
  alerts_by_severity: {},
  alerts_by_category: {},
  alerts_by_status: {},
  alerts_by_source: {},
  alert_activity_by_day: [],
  top_source_ips: {},
  incidents_by_status: {},
  analysis_runs_by_status: {},
  active_models: [],
}

export const COMPONENTS = {
  components: {
    database: { status: 'ok', detail: null },
    dataset_model: { status: 'unavailable', detail: 'No active model' },
    collectors: { status: 'not_configured', detail: 'No collectors registered' },
  },
}
