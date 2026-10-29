import type {
  DashboardOut,
  DashboardSummaryQuery,
  IpSummaryOut,
  SubnetSummaryOut,
} from '../../types/api'
import { apiGet, withQuery } from './client'

export function getIpSummary(ip: string, signal?: AbortSignal): Promise<IpSummaryOut> {
  return apiGet<IpSummaryOut>(`/ips/${encodeURIComponent(ip)}`, { signal })
}

export function getSubnetSummary(cidr: string, signal?: AbortSignal): Promise<SubnetSummaryOut> {
  return apiGet<SubnetSummaryOut>(withQuery('/subnets', { cidr }), { signal })
}

export function getDashboard(
  query: DashboardSummaryQuery,
  signal?: AbortSignal,
): Promise<DashboardOut> {
  return apiGet<DashboardOut>(withQuery('/dashboard/summary', query), { signal })
}
