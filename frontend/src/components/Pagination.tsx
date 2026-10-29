import { ChevronLeft, ChevronRight } from 'lucide-react'

import { formatCount } from '../lib/format'
import { Button } from './Button'

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)
  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 px-4 py-2 text-sm text-slate-600"
    >
      <p>
        Showing {formatCount(first)}–{formatCount(last)} of {formatCount(total)}
      </p>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          <ChevronLeft aria-hidden="true" className="h-4 w-4" />
          Previous
        </Button>
        <span aria-current="page">
          Page {page} of {pages}
        </span>
        <Button size="sm" onClick={() => onPageChange(page + 1)} disabled={page >= pages}>
          Next
          <ChevronRight aria-hidden="true" className="h-4 w-4" />
        </Button>
      </div>
    </nav>
  )
}
