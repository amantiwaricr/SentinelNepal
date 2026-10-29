import type { ReactNode } from 'react'

import { formatCount } from '../lib/format'

interface CountListProps {
  counts: Record<string, number>
  /** Optional fixed order (e.g. severities); otherwise largest first. */
  order?: readonly string[]
  renderLabel?: (key: string) => ReactNode
  empty?: string
}

/** A breakdown such as "alerts by category", with proportional bars and exact numbers. */
export function CountList({ counts, order, renderLabel, empty = 'None recorded' }: CountListProps) {
  const keys = order
    ? order.filter((k) => (counts[k] ?? 0) > 0)
    : Object.keys(counts).sort((a, b) => (counts[b] ?? 0) - (counts[a] ?? 0))
  if (keys.length === 0) return <p className="text-sm text-slate-500">{empty}</p>
  const max = Math.max(...keys.map((k) => counts[k] ?? 0))
  return (
    <ul className="space-y-1.5">
      {keys.map((key) => {
        const value = counts[key] ?? 0
        return (
          <li key={key} className="text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-slate-700">{renderLabel?.(key) ?? key}</span>
              <span className="tabular-nums font-medium text-slate-900">{formatCount(value)}</span>
            </div>
            <div aria-hidden="true" className="mt-0.5 h-1.5 rounded bg-slate-100">
              <div
                className="h-1.5 rounded bg-cyan-600"
                style={{ width: `${max ? (value / max) * 100 : 0}%` }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
