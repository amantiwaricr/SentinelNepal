import { AlertTriangle } from 'lucide-react'

import type { ApiError } from '../services/api/client'

interface ErrorStateProps {
  title: string
  error: ApiError
  onRetry?: () => void
}

export function ErrorState({ title, error, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm">
      <div className="flex items-center gap-2 font-medium text-red-800">
        <AlertTriangle aria-hidden="true" className="h-4 w-4" />
        {title}
      </div>
      <p className="mt-1 text-red-700">{error.message}</p>
      {error.requestId && (
        <p className="mt-1 font-mono text-xs text-red-700">Request ID: {error.requestId}</p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md bg-white px-3 py-1.5 font-medium text-red-800 ring-1 ring-red-300 hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-600"
        >
          Try again
        </button>
      )}
    </div>
  )
}
