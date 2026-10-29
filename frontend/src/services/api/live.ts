import type {
  CollectorModeIn,
  CollectorOut,
  LiveStatusOut,
  ModelVersionOut,
  RecentFlowOut,
} from '../../types/api'
import { apiGet, apiPatch, apiPost } from './client'

export function getLiveStatus(signal?: AbortSignal): Promise<LiveStatusOut> {
  return apiGet<LiveStatusOut>('/live/status', { signal })
}

export function listCollectors(signal?: AbortSignal): Promise<CollectorOut[]> {
  return apiGet<CollectorOut[]>('/collectors', { signal })
}

export function listRecentFlows(signal?: AbortSignal): Promise<RecentFlowOut[]> {
  return apiGet<RecentFlowOut[]>('/live/flows', { signal })
}

export function setCollectorMode(
  collectorId: number,
  mode: CollectorModeIn['mode'],
): Promise<CollectorOut> {
  return apiPatch<CollectorOut>(`/collectors/${collectorId}`, { mode })
}

export function setLiveApproval(modelId: number, approved: boolean): Promise<ModelVersionOut> {
  return apiPost<ModelVersionOut>(`/models/${modelId}/live-approval`, { approved })
}
