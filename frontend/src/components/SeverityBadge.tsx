import type { Severity } from '../types/api'

const SEVERITY_CLASSES: Record<Severity, string> = {
  critical: 'bg-red-600 text-white ring-red-700',
  high: 'bg-orange-100 text-orange-900 ring-orange-600/40',
  medium: 'bg-amber-50 text-amber-900 ring-amber-600/40',
  low: 'bg-slate-100 text-slate-700 ring-slate-500/30',
}

/** Severity is derived from the predicted category and score by a fixed rule (see backend). */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold capitalize ring-1 ring-inset ${SEVERITY_CLASSES[severity]}`}
    >
      {severity}
    </span>
  )
}
