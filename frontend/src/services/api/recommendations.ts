import type { RuleOut } from '../../types/api'
import { apiGet } from './client'

/** The rule catalogue that produces recommendations (for transparency). */
export function listRecommendationRules(signal?: AbortSignal): Promise<RuleOut[]> {
  return apiGet<RuleOut[]>('/recommendations/rules', { signal })
}
