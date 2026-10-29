import { Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

interface NoticeProps {
  tone?: 'info' | 'warning'
  title?: string
  children: ReactNode
}

/** An inline explanation, e.g. that scores are uncalibrated or a feature is not built yet. */
export function Notice({ tone = 'info', title, children }: NoticeProps) {
  const Icon = tone === 'warning' ? TriangleAlert : Info
  const style =
    tone === 'warning'
      ? 'border-amber-200 bg-amber-50 text-amber-900'
      : 'border-sky-200 bg-sky-50 text-sky-900'
  return (
    <div className={`flex gap-2 rounded-md border px-3 py-2 text-sm ${style}`}>
      <Icon aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        {title && <p className="font-medium">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  )
}
