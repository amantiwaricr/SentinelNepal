import { Plus } from 'lucide-react'
import { useCallback } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useCurrentUser } from '../auth/AuthContext'
import { useUserName } from '../auth/userDirectoryContext'
import { DataTable } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SelectFilter } from '../components/FilterFields'
import { FirewallStatusBadge } from '../components/FirewallBits'
import { KeyValueList } from '../components/KeyValueList'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { useApiResource } from '../hooks/useApiResource'
import { executionSummary, reversalSummary } from '../lib/firewall'
import { formatDateTime, formatDuration } from '../lib/format'
import { FIREWALL_STATUS_LABELS, FIREWALL_STATUSES } from '../lib/labels'
import { oneOf, positiveInt } from '../lib/params'
import { getFirewallStatus, listFirewallRequests } from '../services/api/firewall'

const PAGE_SIZE = 25

export function FirewallPage() {
  const user = useCurrentUser()
  const userName = useUserName()
  const [params, setParams] = useSearchParams()
  const status = oneOf(params.get('status'), FIREWALL_STATUSES)
  const page = positiveInt(params.get('page')) ?? 1
  const load = useCallback(
    (signal: AbortSignal) => listFirewallRequests({ status, page, page_size: PAGE_SIZE }, signal),
    [status, page],
  )
  const { state, reload } = useApiResource(load)

  return (
    <>
      <PageHeader
        title="Firewall Approvals"
        description="Requests to temporarily block an address. Every block needs an administrator's explicit approval; nothing is ever blocked automatically from a prediction."
        actions={
          <Link
            to="/firewall/new"
            className="inline-flex items-center gap-1.5 rounded-md bg-cyan-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-cyan-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600 focus-visible:ring-offset-1"
          >
            <Plus aria-hidden="true" className="h-4 w-4" />
            New request
          </Link>
        }
      />
      <div className="mb-4">
        <Notice tone="warning" title="No firewall changes are made yet">
          The nftables helper is added in Phase 7. Until then, approving a request records the
          decision only; the execution result shows “Not executed” and nothing is applied.
        </Notice>
      </div>

      {user.role === 'admin' && <HelperStatusPanel />}

      <Panel className="mb-4">
        <div className="max-w-xs">
          <SelectFilter
            label="Status"
            value={status ?? ''}
            onChange={(value) => setParams(value ? { status: value } : {})}
            options={FIREWALL_STATUSES.map((s) => [s, FIREWALL_STATUS_LABELS[s]])}
          />
        </div>
      </Panel>

      <Panel flush>
        {state.status === 'loading' && <LoadingState label="Loading requests…" />}
        {state.status === 'error' && (
          <div className="p-4">
            <ErrorState title="Requests unavailable" error={state.error} onRetry={reload} />
          </div>
        )}
        {state.status === 'success' && (
          <>
            <DataTable
              caption="Firewall block requests"
              rows={state.data.items}
              rowKey={(r) => r.id}
              empty={<EmptyState title="No block requests" />}
              columns={[
                {
                  key: 'target',
                  header: 'Target',
                  render: (r) => (
                    <Link
                      to={`/firewall/${r.id}`}
                      className="font-mono font-medium text-cyan-700 hover:underline"
                    >
                      {r.target}
                    </Link>
                  ),
                },
                {
                  key: 'reason',
                  header: 'Reason',
                  render: (r) => (
                    <span className="line-clamp-2 max-w-xs text-slate-700">{r.reason}</span>
                  ),
                },
                {
                  key: 'requester',
                  header: 'Requested by',
                  render: (r) => (
                    <div>
                      <div>{userName(r.requested_by)}</div>
                      <div className="text-xs text-slate-500">{formatDateTime(r.created_at)}</div>
                    </div>
                  ),
                },
                {
                  key: 'status',
                  header: 'Approval status',
                  render: (r) => (
                    <div className="space-y-1">
                      <FirewallStatusBadge status={r.status} />
                      {r.dry_run && <StatusBadge tone="neutral" label="Dry run" />}
                    </div>
                  ),
                },
                {
                  key: 'expiry',
                  header: 'Duration / expiry',
                  render: (r) => (
                    <div className="text-xs">
                      <div>{formatDuration(r.duration_seconds)}</div>
                      <div className="text-slate-500">
                        {r.expires_at
                          ? `Expires ${formatDateTime(r.expires_at)}`
                          : 'No expiry (not applied)'}
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'result',
                  header: 'Execution result',
                  render: (r) => (
                    <span className="text-xs text-slate-700">{executionSummary(r)}</span>
                  ),
                },
                {
                  key: 'reversal',
                  header: 'Reversal',
                  render: (r) => (
                    <span className="text-xs text-slate-700">{reversalSummary(r, userName)}</span>
                  ),
                },
              ]}
            />
            {state.data.total > 0 && (
              <Pagination
                page={state.data.page}
                pageSize={state.data.page_size}
                total={state.data.total}
                onPageChange={(p) => {
                  const next = new URLSearchParams(params)
                  next.set('page', String(p))
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

function HelperStatusPanel() {
  const { state } = useApiResource(getFirewallStatus)
  if (state.status !== 'success') return null
  const s = state.data
  return (
    <Panel title="Firewall helper" className="mb-4">
      <KeyValueList
        columns={3}
        items={[
          {
            label: 'Helper',
            value: (
              <StatusBadge
                tone="neutral"
                label={s.helper === 'not_configured' ? 'Not configured' : s.helper}
              />
            ),
          },
          { label: 'Maximum block duration', value: formatDuration(s.max_duration_seconds) },
          {
            label: 'Self-approval',
            value: s.self_approval_allowed
              ? 'Allowed (lab setting)'
              : 'Not allowed: a second admin must approve',
          },
          {
            label: 'Protected networks (never blocked)',
            value: s.protected_networks.length ? (
              <span className="font-mono text-xs">{s.protected_networks.join(', ')}</span>
            ) : (
              'None configured'
            ),
          },
        ]}
      />
      <p className="mt-3 text-xs text-slate-500">{s.detail}</p>
    </Panel>
  )
}
