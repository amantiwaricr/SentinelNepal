import type { LivenessOut, ReadinessOut } from '../../types/api'
import { apiGet } from './client'

export function getLiveness(signal?: AbortSignal): Promise<LivenessOut> {
  return apiGet<LivenessOut>('/health/live', { signal })
}

/** 503 is a valid answer here: it carries the component breakdown of what is not ready. */
export function getReadiness(signal?: AbortSignal): Promise<ReadinessOut> {
  return apiGet<ReadinessOut>('/health/ready', { signal, acceptStatuses: [503] })
}
