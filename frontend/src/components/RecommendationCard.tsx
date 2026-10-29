import { CircleCheck, CircleX } from 'lucide-react'

import type { Tone } from '../lib/labels'
import type { RecommendationOut } from '../types/api'
import { StatusBadge } from './StatusBadge'

const PRIORITY_TONE: Record<RecommendationOut['priority'], Tone> = {
  high: 'danger',
  medium: 'warning',
  low: 'neutral',
}

/**
 * One rule-based recommendation with the evidence it was based on. Evidence that was missing
 * is shown as such, so a cautious "investigate further" suggestion explains itself.
 */
export function RecommendationCard({ recommendation: r }: { recommendation: RecommendationOut }) {
  const evidence = Object.entries(r.evidence_present)
  return (
    <article className="rounded-md border border-slate-200 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={PRIORITY_TONE[r.priority]} label={`${r.priority} priority`} />
        {r.requires_human_approval ? (
          <StatusBadge tone="warning" label="Needs human approval" />
        ) : (
          <StatusBadge tone="info" label="Investigation only" />
        )}
        <span className="font-mono text-xs text-slate-500">
          {r.rule_id} v{r.rule_version}
        </span>
      </div>
      <p className="mt-2 font-medium text-slate-900">{r.action}</p>
      <p className="mt-1 text-slate-600">{r.reason}</p>
      {evidence.length > 0 && (
        <div className="mt-2">
          <h4 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Evidence checked
          </h4>
          <ul className="mt-1 space-y-1">
            {evidence.map(([name, e]) => (
              <li key={name} className="flex items-start gap-1.5 text-xs">
                {e.met ? (
                  <CircleCheck
                    aria-hidden="true"
                    className="mt-px h-3.5 w-3.5 shrink-0 text-emerald-600"
                  />
                ) : (
                  <CircleX aria-hidden="true" className="mt-px h-3.5 w-3.5 shrink-0 text-red-600" />
                )}
                <span className="text-slate-700">
                  <span className="sr-only">{e.met ? 'Met: ' : 'Missing: '}</span>
                  {e.description} <span className="text-slate-500">({e.observed})</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-2 text-xs text-slate-500">
        <span className="font-medium">Limitations:</span> {r.limitations}
      </p>
    </article>
  )
}
