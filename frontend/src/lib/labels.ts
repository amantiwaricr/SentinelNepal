import type {
  AlertSource,
  AlertStatus,
  AnalysisStatus,
  AttackCategory,
  FirewallStatus,
  IncidentStatus,
  Severity,
} from '../types/api'

export type Tone = 'success' | 'warning' | 'danger' | 'neutral' | 'info'

export const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const satisfies Severity[]

export const ATTACK_CATEGORIES = [
  'Analysis',
  'Backdoor',
  'DoS',
  'Exploits',
  'Fuzzers',
  'Generic',
  'Reconnaissance',
  'Shellcode',
  'Worms',
] as const satisfies AttackCategory[]

export const ALERT_STATUSES = [
  'new',
  'acknowledged',
  'linked',
  'dismissed',
] as const satisfies AlertStatus[]

export const ALERT_SOURCES = ['dataset', 'replay', 'live'] as const satisfies AlertSource[]

export const INCIDENT_STATUSES = [
  'new',
  'under_investigation',
  'confirmed',
  'false_positive',
  'resolved',
] as const satisfies IncidentStatus[]

export const FIREWALL_STATUSES = [
  'pending',
  'approved',
  'rejected',
  'executing',
  'active',
  'failed',
  'expired',
  'revoke_requested',
  'revoked',
  'unknown',
] as const satisfies FirewallStatus[]

export const ALERT_STATUS_LABELS: Record<AlertStatus, string> = {
  new: 'New',
  acknowledged: 'Acknowledged',
  linked: 'Linked to incident',
  dismissed: 'Dismissed',
}

export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  new: 'New',
  under_investigation: 'Under investigation',
  confirmed: 'Confirmed',
  false_positive: 'False positive',
  resolved: 'Resolved',
}

export const FIREWALL_STATUS_LABELS: Record<FirewallStatus, string> = {
  pending: 'Pending approval',
  approved: 'Approved (not applied)',
  rejected: 'Rejected',
  executing: 'Executing',
  active: 'Active',
  failed: 'Failed',
  expired: 'Expired',
  revoke_requested: 'Revoke requested',
  revoked: 'Revoked',
  unknown: 'Unknown',
}

export const ALERT_STATUS_TONE: Record<AlertStatus, Tone> = {
  new: 'info',
  acknowledged: 'neutral',
  linked: 'success',
  dismissed: 'neutral',
}

export const INCIDENT_STATUS_TONE: Record<IncidentStatus, Tone> = {
  new: 'info',
  under_investigation: 'warning',
  confirmed: 'danger',
  false_positive: 'neutral',
  resolved: 'success',
}

export const FIREWALL_STATUS_TONE: Record<FirewallStatus, Tone> = {
  pending: 'warning',
  approved: 'info',
  rejected: 'neutral',
  executing: 'info',
  active: 'danger',
  failed: 'danger',
  expired: 'neutral',
  revoke_requested: 'warning',
  revoked: 'neutral',
  unknown: 'warning',
}

export const ANALYSIS_STATUS_TONE: Record<AnalysisStatus, Tone> = {
  queued: 'neutral',
  running: 'info',
  completed: 'success',
  failed: 'danger',
}

export const SOURCE_LABELS: Record<AlertSource, string> = {
  dataset: 'Dataset',
  replay: 'Replay',
  live: 'Live',
}
