import { Search, X } from 'lucide-react'
import { useCallback, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { Button } from '../components/Button'
import { DataTable } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SelectFilter, TextFilter } from '../components/FilterFields'
import { Field } from '../components/FormField'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { useApiResource } from '../hooks/useApiResource'
import { formatDateTime, isoToLocalInput, localInputToIso } from '../lib/format'
import type { Tone } from '../lib/labels'
import { oneOf, positiveInt, text, toSearchParams } from '../lib/params'
import { listAuditLogs } from '../services/api/audit'
import type { AuditOutcome, ListAuditLogsQuery } from '../types/api'

const PAGE_SIZE = 50
const OUTCOMES = ['success', 'failure', 'denied'] as const satisfies AuditOutcome[]
const OUTCOME_TONE: Record<AuditOutcome, Tone> = {
  success: 'success',
  failure: 'danger',
  denied: 'warning',
}

type Draft = Record<
  'actor' | 'action' | 'target_type' | 'target_id' | 'outcome' | 'from' | 'to',
  string
>

export function AuditLogsPage() {
  const [params, setParams] = useSearchParams()
  const query: ListAuditLogsQuery = {
    actor: text(params.get('actor')),
    action: text(params.get('action')),
    target_type: text(params.get('target_type')),
    target_id: text(params.get('target_id')),
    outcome: oneOf(params.get('outcome'), OUTCOMES),
    occurred_from: text(params.get('occurred_from')),
    occurred_to: text(params.get('occurred_to')),
    page: positiveInt(params.get('page')) ?? 1,
    page_size: PAGE_SIZE,
  }
  const queryKey = toSearchParams(query).toString()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- queryKey captures every field of query
  const load = useCallback((signal: AbortSignal) => listAuditLogs(query, signal), [queryKey])
  const { state, reload } = useApiResource(load)

  const initialDraft = (): Draft => ({
    actor: query.actor ?? '',
    action: query.action ?? '',
    target_type: query.target_type ?? '',
    target_id: query.target_id ?? '',
    outcome: query.outcome ?? '',
    from: isoToLocalInput(query.occurred_from),
    to: isoToLocalInput(query.occurred_to),
  })
  const [draft, setDraft] = useState<Draft>(initialDraft)
  const [draftKey, setDraftKey] = useState(queryKey)
  if (draftKey !== queryKey) {
    setDraftKey(queryKey)
    setDraft(initialDraft())
  }
  const update = (field: keyof Draft) => (value: string) =>
    setDraft((d) => ({ ...d, [field]: value }))

  function apply(event: FormEvent) {
    event.preventDefault()
    setParams(
      toSearchParams({
        actor: draft.actor.trim(),
        action: draft.action.trim(),
        target_type: draft.target_type.trim(),
        target_id: draft.target_id.trim(),
        outcome: draft.outcome,
        occurred_from: localInputToIso(draft.from),
        occurred_to: localInputToIso(draft.to),
      }),
    )
  }

  return (
    <>
      <PageHeader
        title="Audit Logs"
        description="Append-only record of security-relevant actions. Entries cannot be edited or deleted, by the API or by the database."
      />
      <Panel className="mb-4">
        <form onSubmit={apply} aria-label="Audit log filters" className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <TextFilter label="Actor (username)" value={draft.actor} onChange={update('actor')} />
            <TextFilter
              label="Action"
              value={draft.action}
              onChange={update('action')}
              placeholder="e.g. auth.login"
            />
            <TextFilter
              label="Target type"
              value={draft.target_type}
              onChange={update('target_type')}
              placeholder="e.g. incident"
            />
            <TextFilter label="Target ID" value={draft.target_id} onChange={update('target_id')} />
            <SelectFilter
              label="Outcome"
              value={draft.outcome}
              onChange={update('outcome')}
              options={OUTCOMES.map((o) => [o, o.charAt(0).toUpperCase() + o.slice(1)])}
            />
            <Field label="From">
              {(props) => (
                <input
                  {...props}
                  type="datetime-local"
                  value={draft.from}
                  onChange={(e) => update('from')(e.target.value)}
                />
              )}
            </Field>
            <Field label="To">
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
          <div className="flex gap-2">
            <Button type="submit" variant="primary">
              <Search aria-hidden="true" className="h-4 w-4" />
              Apply filters
            </Button>
            {[...params.keys()].some((k) => k !== 'page') && (
              <Button onClick={() => setParams({})}>
                <X aria-hidden="true" className="h-4 w-4" />
                Clear
              </Button>
            )}
          </div>
        </form>
      </Panel>

      <Panel flush>
        {state.status === 'loading' && <LoadingState label="Loading audit log…" />}
        {state.status === 'error' && (
          <div className="p-4">
            <ErrorState title="Audit log unavailable" error={state.error} onRetry={reload} />
          </div>
        )}
        {state.status === 'success' && (
          <>
            <DataTable
              caption="Audit log entries"
              rows={state.data.items}
              rowKey={(e) => e.id}
              empty={<EmptyState title="No audit entries match" />}
              columns={[
                {
                  key: 'when',
                  header: 'Time',
                  className: 'whitespace-nowrap',
                  render: (e) => formatDateTime(e.occurred_at),
                },
                {
                  key: 'actor',
                  header: 'Actor',
                  render: (e) => (
                    <div>
                      <div>{e.actor_label ?? '—'}</div>
                      <div className="text-xs text-slate-500">{e.actor_type}</div>
                    </div>
                  ),
                },
                {
                  key: 'action',
                  header: 'Action',
                  className: 'font-mono text-xs',
                  render: (e) => e.action,
                },
                {
                  key: 'target',
                  header: 'Target',
                  className: 'text-xs',
                  render: (e) => (e.target_type ? `${e.target_type} ${e.target_id ?? ''}` : '—'),
                },
                {
                  key: 'outcome',
                  header: 'Outcome',
                  render: (e) => <StatusBadge tone={OUTCOME_TONE[e.outcome]} label={e.outcome} />,
                },
                {
                  key: 'source',
                  header: 'IP / request',
                  className: 'font-mono text-xs',
                  render: (e) => (
                    <div>
                      <div>{e.ip_address ?? '—'}</div>
                      <div className="text-slate-500" title={e.request_id ?? undefined}>
                        {e.request_id ? e.request_id.slice(0, 8) : ''}
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'details',
                  header: 'Details',
                  render: (e) =>
                    Object.keys(e.details).length === 0 ? (
                      <span className="text-slate-400">—</span>
                    ) : (
                      // Shown as text, never as HTML.
                      <pre className="max-w-sm overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs text-slate-600">
                        {JSON.stringify(e.details)}
                      </pre>
                    ),
                },
              ]}
            />
            {state.data.total > 0 && (
              <Pagination
                page={state.data.page}
                pageSize={state.data.page_size}
                total={state.data.total}
                onPageChange={(page) => {
                  const next = new URLSearchParams(params)
                  next.set('page', String(page))
                  setParams(next)
                }}
              />
            )}
          </>
        )}
      </Panel>
    </>
  )
}
