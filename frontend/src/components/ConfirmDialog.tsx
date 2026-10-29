import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'

import type { ApiError } from '../services/api/client'
import { Button } from './Button'
import { FormError } from './FormError'

interface ConfirmDialogProps {
  title: string
  children?: ReactNode
  confirmLabel: string
  tone?: 'primary' | 'danger'
  /** When set, the confirm button stays disabled until this exact text is typed. */
  requireText?: string
  pending?: boolean
  /** Extra condition for enabling confirm, e.g. a required choice not yet made. */
  confirmDisabled?: boolean
  error?: ApiError | null
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Modal confirmation for consequential actions (firewall approval, model activation).
 * Focus moves into the dialog, Tab stays inside it, Escape cancels, and focus returns to
 * the element that opened it.
 */
export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  tone = 'primary',
  requireText,
  pending = false,
  confirmDisabled = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId()
  const inputId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const [typed, setTyped] = useState('')
  const confirmed = !confirmDisabled && (requireText === undefined || typed.trim() === requireText)

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    const dialog = dialogRef.current
    const first = dialog?.querySelector<HTMLElement>('input, textarea, select, button')
    first?.focus()
    return () => opener?.focus()
  }, [])

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'Escape' && !pending) {
      event.stopPropagation()
      onCancel()
      return
    }
    if (event.key !== 'Tab' || !dialogRef.current) return
    const focusable = Array.from(
      dialogRef.current.querySelectorAll<HTMLElement>(
        'input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled])',
      ),
    )
    const first = focusable[0]
    const last = focusable.at(-1)
    if (!first || !last) return
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (confirmed && !pending) onConfirm()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
        className="w-full max-w-lg rounded-lg bg-white shadow-xl"
      >
        <form onSubmit={submit}>
          <div className="space-y-3 p-5">
            <h2 id={titleId} className="text-lg font-semibold text-slate-900">
              {title}
            </h2>
            {children && <div className="space-y-3 text-sm text-slate-700">{children}</div>}
            {requireText !== undefined && (
              <div>
                <label htmlFor={inputId} className="mb-1 block text-xs font-medium text-slate-700">
                  Type <span className="font-mono font-semibold">{requireText}</span> to confirm
                </label>
                <input
                  id={inputId}
                  value={typed}
                  onChange={(event) => setTyped(event.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  className="block w-full rounded-md border-0 px-2.5 py-1.5 font-mono text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-cyan-600"
                />
              </div>
            )}
            <FormError error={error ?? null} />
          </div>
          <div className="flex justify-end gap-2 rounded-b-lg bg-slate-50 px-5 py-3">
            <Button onClick={onCancel} disabled={pending}>
              Cancel
            </Button>
            <Button type="submit" variant={tone} disabled={!confirmed || pending}>
              {pending ? 'Working…' : confirmLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
