import type { ReactNode } from 'react'

interface PanelProps {
  title?: string
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  /** Remove body padding, e.g. for edge-to-edge tables. */
  flush?: boolean
}

export function Panel({
  title,
  description,
  actions,
  children,
  className = '',
  flush,
}: PanelProps) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-200 px-4 py-3">
          <div>
            {title && <h2 className="font-semibold text-slate-900">{title}</h2>}
            {description && <div className="mt-0.5 text-xs text-slate-500">{description}</div>}
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      <div className={flush ? '' : 'p-4'}>{children}</div>
    </section>
  )
}
