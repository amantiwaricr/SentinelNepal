import type {
  FirewallApprove,
  FirewallReject,
  FirewallRequestCreate,
  FirewallRequestOut,
  FirewallRevoke,
  FirewallStatusOut,
  ListRequestsQuery,
  Page,
} from '../../types/api'
import { apiGet, apiPost, withQuery } from './client'

export function listFirewallRequests(
  query: ListRequestsQuery,
  signal?: AbortSignal,
): Promise<Page<FirewallRequestOut>> {
  return apiGet<Page<FirewallRequestOut>>(withQuery('/firewall/requests', query), { signal })
}

export function getFirewallRequest(
  requestId: number,
  signal?: AbortSignal,
): Promise<FirewallRequestOut> {
  return apiGet<FirewallRequestOut>(`/firewall/requests/${requestId}`, { signal })
}

export function createFirewallRequest(body: FirewallRequestCreate): Promise<FirewallRequestOut> {
  return apiPost<FirewallRequestOut>('/firewall/requests', body)
}

export function approveFirewallRequest(
  requestId: number,
  body: FirewallApprove,
): Promise<FirewallRequestOut> {
  return apiPost<FirewallRequestOut>(`/firewall/requests/${requestId}/approve`, body)
}

export function rejectFirewallRequest(
  requestId: number,
  body: FirewallReject,
): Promise<FirewallRequestOut> {
  return apiPost<FirewallRequestOut>(`/firewall/requests/${requestId}/reject`, body)
}

export function revokeFirewallRequest(
  requestId: number,
  body: FirewallRevoke,
): Promise<FirewallRequestOut> {
  return apiPost<FirewallRequestOut>(`/firewall/requests/${requestId}/revoke`, body)
}

/** Admin only: helper state and the configured protected networks. */
export function getFirewallStatus(signal?: AbortSignal): Promise<FirewallStatusOut> {
  return apiGet<FirewallStatusOut>('/firewall/status', { signal })
}
