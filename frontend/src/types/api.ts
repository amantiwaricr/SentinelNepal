/**
 * API types. Response and request shapes are generated from the backend's OpenAPI schema
 * into api.gen.ts; this module re-exports them and adds the few names the generator cannot
 * produce (the generic Page<T>, the error envelope, and aliases for inline unions).
 */
import type {
  AlertOut,
  AnalysisRunOut,
  AuditLogOut,
  ComponentStatus,
  DashboardOut,
  FirewallRequestOut,
  IncidentOut,
  ListAlertsQuery,
  UserOut,
} from './api.gen'

export type * from './api.gen'

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details: unknown
    request_id: string | null
  }
}

export type Role = UserOut['role']
export type ComponentState = ComponentStatus['status']
export type AlertSource = AlertOut['source']
export type AlertStatus = AlertOut['status']
export type AttackCategory = AlertOut['predicted_category']
export type Severity = AlertOut['severity']
export type IncidentStatus = IncidentOut['status']
export type FirewallStatus = FirewallRequestOut['status']
export type AnalysisStatus = AnalysisRunOut['status']
export type AuditOutcome = AuditLogOut['outcome']
export type DashboardSource = DashboardOut['source']
export type AlertSort = NonNullable<ListAlertsQuery['sort']>
