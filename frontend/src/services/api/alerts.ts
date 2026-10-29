import type {
  AlertDetail,
  AlertOut,
  AlertStatusUpdate,
  ListAlertsQuery,
  Page,
  RecommendationOut,
} from '../../types/api'
import { apiGet, apiPatch, withQuery } from './client'

export function listAlerts(query: ListAlertsQuery, signal?: AbortSignal): Promise<Page<AlertOut>> {
  return apiGet<Page<AlertOut>>(withQuery('/alerts', query), { signal })
}

export function getAlert(alertId: number, signal?: AbortSignal): Promise<AlertDetail> {
  return apiGet<AlertDetail>(`/alerts/${alertId}`, { signal })
}

export function updateAlertStatus(alertId: number, body: AlertStatusUpdate): Promise<AlertOut> {
  return apiPatch<AlertOut>(`/alerts/${alertId}`, body)
}

export function listRecommendations(
  alertId: number,
  signal?: AbortSignal,
): Promise<RecommendationOut[]> {
  return apiGet<RecommendationOut[]>(withQuery('/recommendations', { alert_id: alertId }), {
    signal,
  })
}
