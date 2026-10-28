import { RefreshCw } from 'lucide-react'

import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import { useApiResource } from '../hooks/useApiResource'
import { getReadiness } from '../services/api/health'
import type { ComponentState } from '../types/api'

const COMPONENT_LABELS: Record<string, string> = {
  database: 'Database',
  migrations: 'Database migrations',
}

const STATE_TONE = {
  ok: 'success',
  pending: 'warning',
  unavailable: 'danger',
  unknown: 'neutral',
  not_configured: 'neutral',
} as const satisfies Record<ComponentState, string>

export function SystemHealthPage() {
  const { state, reload } = useApiResource(getReadiness)

  return (
    <>
      <PageHeader
        title="System Health"
        description="Status reported by the backend's readiness check."
        actions={
          <button
            type="button"
            onClick={reload}
            className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600"
          >
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
            Refresh
          </button>
        }
      />

      {state.status === 'loading' && <LoadingState label="Checking backend status…" />}

      {state.status === 'error' && (
        <ErrorState title="Backend status unavailable" error={state.error} onRetry={reload} />
      )}

      {state.status === 'success' && (
        <section className="rounded-lg border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 p-4">
            <h2 className="font-medium text-slate-900">Backend API</h2>
            <StatusBadge
              tone={state.data.status === 'ready' ? 'success' : 'danger'}
              label={state.data.status === 'ready' ? 'Ready' : 'Not ready'}
            />
            <span className="text-sm text-slate-500">
              v{state.data.version} · {state.data.environment}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Component
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Detail
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {Object.entries(state.data.components).map(([name, component]) => (
                  <tr key={name}>
                    <td className="px-4 py-2 font-medium text-slate-800">
                      {COMPONENT_LABELS[name] ?? name}
                    </td>
                    <td className="px-4 py-2">
                      <StatusBadge tone={STATE_TONE[component.status]} label={component.status} />
                    </td>
                    <td className="px-4 py-2 text-slate-600">{component.detail ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-slate-200 p-4 text-xs text-slate-500">
            Model, collector, and firewall-helper status will appear here once those components
            exist (Phases 2, 6, and 7).
          </p>
        </section>
      )}
    </>
  )
}
