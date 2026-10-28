type Tone = 'success' | 'warning' | 'danger' | 'neutral'

const TONE_CLASSES: Record<Tone, string> = {
  success: 'bg-emerald-50 text-emerald-800 ring-emerald-600/30',
  warning: 'bg-amber-50 text-amber-800 ring-amber-600/30',
  danger: 'bg-red-50 text-red-800 ring-red-600/30',
  neutral: 'bg-slate-100 text-slate-700 ring-slate-500/30',
}

interface StatusBadgeProps {
  tone: Tone
  label: string
}

export function StatusBadge({ tone, label }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASSES[tone]}`}
    >
      {label}
    </span>
  )
}
