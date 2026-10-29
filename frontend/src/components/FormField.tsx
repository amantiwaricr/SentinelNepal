import { useId, type ReactNode } from 'react'

const CONTROL =
  'block w-full rounded-md border-0 bg-white px-2.5 py-1.5 text-sm text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-cyan-600 disabled:bg-slate-50 disabled:text-slate-500'

interface FieldProps {
  label: string
  hint?: ReactNode
  error?: string | null
  className?: string
  children: (props: {
    id: string
    className: string
    'aria-describedby'?: string
    'aria-invalid'?: boolean
  }) => ReactNode
}

/** Label, control, hint and error wired together with ids for screen readers. */
export function Field({ label, hint, error, className = '', children }: FieldProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ')
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-700">
        {label}
      </label>
      {children({
        id,
        className: CONTROL,
        'aria-describedby': describedBy || undefined,
        'aria-invalid': error ? true : undefined,
      })}
      {hint && (
        <p id={hintId} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1 text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
