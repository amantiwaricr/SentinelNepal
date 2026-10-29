import type { AnalysisRunOut, ListRunsQuery, Page } from '../../types/api'
import { apiGet, apiPost, withQuery } from './client'

export function listAnalysisRuns(
  query: ListRunsQuery,
  signal?: AbortSignal,
): Promise<Page<AnalysisRunOut>> {
  return apiGet<Page<AnalysisRunOut>>(withQuery('/datasets/analyses', query), { signal })
}

export function getAnalysisRun(runId: number, signal?: AbortSignal): Promise<AnalysisRunOut> {
  return apiGet<AnalysisRunOut>(`/datasets/analyses/${runId}`, { signal })
}

/** Queues a UNSW-NB15-format CSV for analysis; the server names and stores the file. */
export function uploadDataset(file: File): Promise<AnalysisRunOut> {
  const form = new FormData()
  form.append('file', file)
  return apiPost<AnalysisRunOut>('/datasets/analyses', form)
}
