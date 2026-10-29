import type { FirewallRequestOut } from '../types/api'
import { formatDateTime } from './format'

/**
 * What actually happened on the firewall. "Applied" is shown only when the helper has
 * confirmed the rule (`applied` from the API); an approval alone never counts.
 */
export function executionSummary(request: FirewallRequestOut): string {
  const last = request.results?.at(-1)
  if (request.applied) return `Applied ${formatDateTime(request.applied_at)}`
  if (last) {
    return last.success
      ? `${last.operation} succeeded ${formatDateTime(last.executed_at)}`
      : `${last.operation} failed: ${last.error_message ?? last.error_code ?? 'no detail'}`
  }
  if (request.status === 'pending') return 'Awaiting decision'
  if (request.status === 'rejected') return 'Not executed (rejected)'
  return 'Not executed: no firewall helper (added in Phase 7)'
}

export function reversalSummary(
  request: FirewallRequestOut,
  userName: (id: number | null) => string,
): string {
  if (request.revoked_at)
    return `Revoked by ${userName(request.revoked_by)}, ${formatDateTime(request.revoked_at)}`
  if (request.status === 'revoke_requested') return 'Revocation requested'
  if (request.status === 'expired') return 'Expired'
  if (request.status === 'approved' || request.status === 'active') return 'Not revoked'
  return '—'
}
