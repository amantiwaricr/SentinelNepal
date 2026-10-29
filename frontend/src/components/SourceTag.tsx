import { Database, Radio, RotateCcw } from 'lucide-react'

import { SOURCE_LABELS } from '../lib/labels'
import type { AlertSource } from '../types/api'

const STYLES: Record<AlertSource, string> = {
  dataset: 'border-violet-300 bg-violet-50 text-violet-800',
  replay: 'border-sky-300 bg-sky-50 text-sky-800',
  live: 'border-emerald-400 bg-emerald-50 text-emerald-800',
}

const ICONS = { dataset: Database, replay: RotateCcw, live: Radio }

/**
 * Marks where an alert came from. Dataset-analysis results (uploaded UNSW-NB15 files) must
 * never be mistaken for live traffic, so every alert view shows this tag.
 */
export function SourceTag({ source }: { source: AlertSource }) {
  const Icon = ICONS[source]
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STYLES[source]}`}
    >
      <Icon aria-hidden="true" className="h-3 w-3" />
      {SOURCE_LABELS[source]}
    </span>
  )
}
