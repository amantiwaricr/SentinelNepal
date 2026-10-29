import { Search, X } from 'lucide-react'
import { useCallback, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { AlertTable } from '../components/AlertTable'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SelectFilter, TextFilter } from '../components/FilterFields'
import { Field } from '../components/FormField'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { Panel } from '../components/Panel'
import { useApiResource } from '../hooks/useApiResource'
import { isoToLocalInput, localInputToIso } from '../lib/format'
import {
  ALERT_SOURCES,
  ALERT_STATUS_LABELS,
  ALERT_STATUSES,
  ATTACK_CATEGORIES,
  SEVERITIES,
  SOURCE_LABELS,
} from '../lib/labels'
import { oneOf, positiveInt, text, toSearchParams } from '../lib/params'
import { listAlerts } from '../services/api/alerts'
import type { AlertSort, ListAlertsQuery } from '../types/api'

const PAGE_SIZE = 25
const SORTS: { value: AlertSort; label: string }[] = [
  { value: '-created_at', label: 'Newest first' },
  { value: 'created_at', label: 'Oldest first' },
  { value: '-attack_score', label: 'Highest score first' },
  { value: 'attack_score', label: 'Lowest score first' },
]
const SORT_VALUES = SORTS.map((s) => s.value)

/** Filters live in the URL, so a filtered view can be bookmarked or shared with a colleague. */
function queryFromParams(params: URLSearchParams): ListAlertsQuery {
  return {
    src_ip: text(params.get('src_ip')),
    dst_ip: text(params.get('dst_ip')),
    cidr: text(params.get('cidr')),
    category: oneOf(params.get('category'), ATTACK_CATEGORIES),
    severity: oneOf(params.get('severity'), SEVERITIES),
    status: oneOf(params.get('status'), ALERT_STATUSES),
    source: oneOf(params.get('source'), ALERT_SOURCES),
    run_id: positiveInt(params.get('run_id')),
    created_from: text(params.get('created_from')),
    created_to: text(params.get('created_to')),
    sort: oneOf(params.get('sort'), SORT_VALUES) ?? '-created_at',
    page: positiveInt(params.get('page')) ?? 1,
    page_size: PAGE_SIZE,
  }
}

type Draft = Record<
  'src_ip' | 'dst_ip' | 'cidr' | 'category' | 'severity' | 'status' | 'source' | 'from' | 'to',
  string
>

function draftFrom(query: ListAlertsQuery): Draft {
  return {
    src_ip: query.src_ip ?? '',
    dst_ip: query.dst_ip ?? '',
    cidr: query.cidr ?? '',
    category: query.category ?? '',
    severity: query.severity ?? '',
    status: query.status ?? '',
    source: query.source ?? '',
    from: isoToLocalInput(query.created_from),
    to: isoToLocalInput(query.created_to),
  }
}

export function AlertsPage() {
  const [params, setParams] = useSearchParams()
  const query = queryFromParams(params)
  const queryKey = toSearchParams(query).toString()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- queryKey captures every field of query
  const load = useCallback((signal: AbortSignal) => listAlerts(query, signal), [queryKey])
  const { state, reload } = useApiResource(load)

  const [draft, setDraft] = useState<Draft>(() => draftFrom(query))
  const [draftKey, setDraftKey] = useState(queryKey)
  // Keep the form in step when the URL changes (back button, links from other pages).
  if (draftKey !== queryKey) {
    setDraftKey(queryKey)
    setDraft(draftFrom(query))
  }

  const update = (field: keyof Draft) => (value: string) =>
    setDraft((current) => ({ ...current, [field]: value }))

  function apply(event: FormEvent) {
    event.preventDefault()
    setParams(
      toSearchParams({
        src_ip: draft.src_ip.trim(),
        dst_ip: draft.dst_ip.trim(),
        cidr: draft.cidr.trim(),
        category: draft.category,
        severity: draft.severity,
        status: draft.status,
        source: draft.source,
        run_id: query.run_id,
        created_from: localInputToIso(draft.from),
        created_to: localInputToIso(draft.to),
        sort: query.sort === '-created_at' ? undefined : query.sort,
      }),
    )
  }

  function setParam(key: string, value: string | number | undefined) {
    const next = new URLSearchParams(params)
    if (value === undefined || value === '') next.delete(key)
    else next.set(key, String(value))
    if (key !== 'page') next.delete('page')
    setParams(next)
  }

  const hasFilters = [...params.keys()].some((k) => k !== 'page' && k !== 'sort')

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Records the model scored at or above the alert threshold. Each alert is a prediction to investigate, not a confirmed attack."
      />

      <Panel className="mb-4">
        <form onSubmit={apply} aria-label="Alert filters" className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <TextFilter label="Source IP" value={draft.src_ip} onChange={update('src_ip')} />
            <TextFilter label="Destination IP" value={draft.dst_ip} onChange={update('dst_ip')} />
            <TextFilter
              label="Source or destination in CIDR"
              value={draft.cidr}
              onChange={update('cidr')}
              placeholder="e.g. 10.0.0.0/24"
            />
            <SelectFilter
              label="Suspected category"
              value={draft.category}
              onChange={update('category')}
              options={ATTACK_CATEGORIES.map((c) => [c, c])}
            />
            <SelectFilter
              label="Severity"
              value={draft.severity}
              onChange={update('severity')}
              options={SEVERITIES.map((s) => [s, s.charAt(0).toUpperCase() + s.slice(1)])}
            />
            <SelectFilter
              label="Status"
              value={draft.status}
              onChange={update('status')}
              options={ALERT_STATUSES.map((s) => [s, ALERT_STATUS_LABELS[s]])}
            />
            <SelectFilter
              label="Source"
              value={draft.source}
              onChange={update('source')}
              options={ALERT_SOURCES.map((s) => [s, SOURCE_LABELS[s]])}
            />
            <div className="grid grid-cols-2 gap-2">
              <Field label="Created from">
                {(props) => (
                  <input
                    {...props}
                    type="datetime-local"
                    value={draft.from}
                    onChange={(e) => update('from')(e.target.value)}
                  />
                )}
              </Field>
              <Field label="Created to">
                {(props) => (
                  <input
                    {...props}
                    type="datetime-local"
                    value={draft.to}
                    onChange={(e) => update('to')(e.target.value)}
                  />
                )}
              </Field>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" variant="primary">
              <Search aria-hidden="true" className="h-4 w-4" />
              Apply filters
            </Button>
            {hasFilters && (
              <Button onClick={() => setParams({})}>
                <X aria-hidden="true" className="h-4 w-4" />
                Clear
              </Button>
            )}
            {query.run_id && (
              <span className="text-sm text-slate-600">
                Showing alerts from analysis run #{query.run_id}
              </span>
            )}
          </div>
        </form>
      </Panel>

      <Panel
        flush
        title="Results"
        actions={
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Sort
            <select
              value={query.sort}
              onChange={(e) =>
                setParam('sort', e.target.value === '-created_at' ? '' : e.target.value)
              }
              className="rounded-md border-0 py-1 pl-2 pr-8 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-cyan-600"
            >
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        }
      >
        {state.status === 'loading' && <LoadingState label="Loading alerts…" />}
        {state.status === 'error' && (
          <div className="p-4">
            <ErrorState title="Alerts unavailable" error={state.error} onRetry={reload} />
          </div>
        )}
        {state.status === 'success' && (
          <>
            <AlertTable
              alerts={state.data.items}
              caption="Alerts matching the filters"
              empty={
                <EmptyState title={hasFilters ? 'No alerts match these filters' : 'No alerts yet'}>
                  {!hasFilters &&
                    'Alerts appear after a dataset file is analysed (Dataset Analysis) or, from Phase 6, from live collectors.'}
                </EmptyState>
              }
            />
            {state.data.total > 0 && (
              <Pagination
                page={state.data.page}
                pageSize={state.data.page_size}
                total={state.data.total}
                onPageChange={(page) => setParam('page', page)}
              />
            )}
          </>
        )}
      </Panel>
    </>
  )
}
