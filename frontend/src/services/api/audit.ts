import type { AuditLogOut, ListAuditLogsQuery, Page } from '../../types/api'
import { apiGet, withQuery } from './client'

export function listAuditLogs(
  query: ListAuditLogsQuery,
  signal?: AbortSignal,
): Promise<Page<AuditLogOut>> {
  return apiGet<Page<AuditLogOut>>(withQuery('/audit-logs', query), { signal })
}
