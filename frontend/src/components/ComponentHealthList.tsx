import { humanize } from '../lib/format'
import type { Tone } from '../lib/labels'
import type { ComponentState, ComponentStatus } from '../types/api'
import { StatusBadge } from './StatusBadge'

const COMPONENT_LABELS: Record<string, string> = {
  database: 'Database',
  migrations: 'Database migrations',
  dataset_model: 'Dataset-analysis model',
  analysis_worker: 'Analysis worker',
  collectors: 'Live collectors',
  firewall_helper: 'Firewall helper',
}

const STATE_TONE = {
  ok: 'success',
  pending: 'warning',
  unavailable: 'danger',
  unknown: 'neutral',
  not_configured: 'neutral',
} as const satisfies Record<ComponentState, Tone>

const STATE_LABEL: Record<ComponentState, string> = {
  ok: 'OK',
  pending: 'Pending',
  unavailable: 'Unavailable',
  unknown: 'Unknown',
  not_configured: 'Not configured',
}

export function ComponentHealthList({
  components,
}: {
  components: Record<string, ComponentStatus>
}) {
  return (
    <ul className="divide-y divide-slate-100">
      {Object.entries(components).map(([name, component]) => (
        <li key={name} className="flex flex-wrap items-start justify-between gap-2 py-2 text-sm">
          <div className="min-w-0">
            <p className="font-medium text-slate-800">{COMPONENT_LABELS[name] ?? humanize(name)}</p>
            {component.detail && <p className="text-xs text-slate-500">{component.detail}</p>}
          </div>
          <StatusBadge tone={STATE_TONE[component.status]} label={STATE_LABEL[component.status]} />
        </li>
      ))}
    </ul>
  )
}
