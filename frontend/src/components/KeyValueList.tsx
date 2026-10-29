import type { ReactNode } from 'react'

export interface KeyValueItem {
  label: string
  value: ReactNode
}

export function KeyValueList({
  items,
  columns = 2,
}: {
  items: KeyValueItem[]
  columns?: 1 | 2 | 3
}) {
  const grid = { 1: '', 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-2 lg:grid-cols-3' }[columns]
  return (
    <dl className={`grid grid-cols-1 gap-x-6 gap-y-3 ${grid}`}>
      {items.map(({ label, value }) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
          <dd className="mt-0.5 break-words text-sm text-slate-900">{value}</dd>
        </div>
      ))}
    </dl>
  )
}
