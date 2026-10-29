import type { ModelVersionOut } from '../../types/api'
import { apiGet, apiPost } from './client'

export function listModels(signal?: AbortSignal): Promise<ModelVersionOut[]> {
  return apiGet<ModelVersionOut[]>('/models', { signal })
}

export function activateModel(modelId: number): Promise<ModelVersionOut> {
  return apiPost<ModelVersionOut>(`/models/${modelId}/activate`)
}
