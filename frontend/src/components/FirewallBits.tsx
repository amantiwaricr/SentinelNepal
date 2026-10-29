import { FIREWALL_STATUS_LABELS, FIREWALL_STATUS_TONE } from '../lib/labels'
import type { FirewallStatus } from '../types/api'
import { StatusBadge } from './StatusBadge'

export function FirewallStatusBadge({ status }: { status: FirewallStatus }) {
  return <StatusBadge tone={FIREWALL_STATUS_TONE[status]} label={FIREWALL_STATUS_LABELS[status]} />
}
