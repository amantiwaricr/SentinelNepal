/** Types mirroring backend response schemas (backend/app/schemas). */

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details: unknown
    request_id: string | null
  }
}

export type ComponentState = 'ok' | 'pending' | 'unavailable' | 'unknown' | 'not_configured'

export interface ComponentStatus {
  status: ComponentState
  detail: string | null
}

export interface LivenessOut {
  status: 'ok'
  service: string
  version: string
}

export interface ReadinessOut {
  status: 'ready' | 'not_ready'
  service: string
  version: string
  environment: string
  components: Record<string, ComponentStatus>
}
