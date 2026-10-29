import type { ApiError } from '../services/api/client'

/** A failed form submission, with the server's message (never a stack trace). */
export function FormError({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
      {error.message}
      {error.requestId && (
        <span className="mt-0.5 block font-mono text-xs text-red-700">
          Request ID: {error.requestId}
        </span>
      )}
    </p>
  )
}
