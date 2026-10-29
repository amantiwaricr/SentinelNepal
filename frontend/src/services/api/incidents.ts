import type {
  AuditLogOut,
  IncidentCreate,
  IncidentDetail,
  IncidentOut,
  IncidentUpdate,
  ListIncidentsQuery,
  NoteOut,
  Page,
} from '../../types/api'
import { apiGet, apiPatch, apiPost, withQuery } from './client'

export function listIncidents(
  query: ListIncidentsQuery,
  signal?: AbortSignal,
): Promise<Page<IncidentOut>> {
  return apiGet<Page<IncidentOut>>(withQuery('/incidents', query), { signal })
}

export function getIncident(incidentId: number, signal?: AbortSignal): Promise<IncidentDetail> {
  return apiGet<IncidentDetail>(`/incidents/${incidentId}`, { signal })
}

export function createIncident(body: IncidentCreate): Promise<IncidentDetail> {
  return apiPost<IncidentDetail>('/incidents', body)
}

export function updateIncident(incidentId: number, body: IncidentUpdate): Promise<IncidentDetail> {
  return apiPatch<IncidentDetail>(`/incidents/${incidentId}`, body)
}

export function linkAlerts(incidentId: number, alertIds: number[]): Promise<IncidentDetail> {
  return apiPost<IncidentDetail>(`/incidents/${incidentId}/alerts`, { alert_ids: alertIds })
}

export function listNotes(incidentId: number, signal?: AbortSignal): Promise<NoteOut[]> {
  return apiGet<NoteOut[]>(`/incidents/${incidentId}/notes`, { signal })
}

export function addNote(incidentId: number, body: string): Promise<NoteOut> {
  return apiPost<NoteOut>(`/incidents/${incidentId}/notes`, { body })
}

export function getIncidentHistory(
  incidentId: number,
  signal?: AbortSignal,
): Promise<AuditLogOut[]> {
  return apiGet<AuditLogOut[]>(`/incidents/${incidentId}/history`, { signal })
}
