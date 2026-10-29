import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router'

import { useCurrentUser } from '../auth/AuthContext'
import { useUserName } from '../auth/userDirectoryContext'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DataTable } from '../components/DataTable'
import { ErrorState } from '../components/ErrorState'
import { FirewallStatusBadge } from '../components/FirewallBits'
import { Field } from '../components/FormField'
import { KeyValueList } from '../components/KeyValueList'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { executionSummary, reversalSummary } from '../lib/firewall'
import { formatDateTime, formatDuration, humanize } from '../lib/format'
import { positiveInt } from '../lib/params'
import {
  approveFirewallRequest,
  getFirewallRequest,
  rejectFirewallRequest,
  revokeFirewallRequest,
} from '../services/api/firewall'
import type { FirewallRequestOut } from '../types/api'

type Decision = 'approve' | 'reject' | 'revoke'
const REVOCABLE = new Set(['approved', 'executing', 'active', 'unknown'])

export function FirewallRequestPage() {
  const requestId = positiveInt(useParams().requestId ?? null)
  if (requestId === undefined) return <PageHeader title="Request not found" />
  return <FirewallRequestDetails requestId={requestId} key={requestId} />
}

function FirewallRequestDetails({ requestId }: { requestId: number }) {
  const load = useCallback(
    (signal: AbortSignal) => getFirewallRequest(requestId, signal),
    [requestId],
  )
  const { state, reload } = useApiResource(load)
  if (state.status === 'loading') return <LoadingState label="Loading request…" />
  if (state.status === 'error') {
    return (
      <>
        <PageHeader title={`Block request ${requestId}`} />
        <ErrorState title="Request unavailable" error={state.error} onRetry={reload} />
      </>
    )
  }
  return <RequestView request={state.data} onChanged={() => reload({ quiet: true })} />
}

function RequestView({
  request,
  onChanged,
}: {
  request: FirewallRequestOut
  onChanged: () => void
}) {
  const user = useCurrentUser()
  const userName = useUserName()
  const [decision, setDecision] = useState<Decision | null>(null)
  const isAdmin = user.role === 'admin'
  const ownRequest = request.requested_by === user.id

  return (
    <>
      <PageHeader
        title={`Block request ${request.id}`}
        description={`Target ${request.target} · requested ${formatDateTime(request.created_at)}`}
        actions={
          isAdmin && (
            <>
              {request.status === 'pending' && (
                <>
                  <Button variant="danger" onClick={() => setDecision('approve')}>
                    Approve block…
                  </Button>
                  <Button onClick={() => setDecision('reject')}>Reject…</Button>
                </>
              )}
              {REVOCABLE.has(request.status) && (
                <Button onClick={() => setDecision('revoke')}>Revoke…</Button>
              )}
            </>
          )
        }
      />

      <div className="mb-4 space-y-2">
        {!request.applied && (
          <Notice tone="warning">
            No firewall rule has been applied for this request. The helper that applies and verifies
            rules is added in Phase 7.
          </Notice>
        )}
        {request.status === 'pending' && !isAdmin && (
          <Notice>An administrator must review and approve this request.</Notice>
        )}
        {request.status === 'pending' && isAdmin && ownRequest && (
          <Notice>
            You made this request. Unless self-approval is enabled for the lab, a different
            administrator must approve it.
          </Notice>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel title="Request" className="xl:col-span-2">
          <KeyValueList
            items={[
              { label: 'Target', value: <span className="font-mono">{request.target}</span> },
              { label: 'IP version', value: `IPv${request.ip_version}` },
              {
                label: 'Approval status',
                value: (
                  <span className="inline-flex gap-1">
                    <FirewallStatusBadge status={request.status} />
                    {request.dry_run && <StatusBadge tone="neutral" label="Dry run" />}
                  </span>
                ),
              },
              { label: 'Requested duration', value: formatDuration(request.duration_seconds) },
              { label: 'Requested by', value: userName(request.requested_by) },
              { label: 'Requested at', value: formatDateTime(request.created_at) },
              {
                label: 'Decision',
                value: request.approved_by
                  ? `${userName(request.approved_by)}, ${formatDateTime(request.approved_at)}`
                  : '—',
              },
              { label: 'Decision note', value: request.decision_note ?? '—' },
              {
                label: 'Applied',
                value: request.applied ? formatDateTime(request.applied_at) : 'No',
              },
              {
                label: 'Expires',
                value: request.expires_at
                  ? formatDateTime(request.expires_at)
                  : 'No expiry (not applied)',
              },
              { label: 'Execution result', value: executionSummary(request) },
              { label: 'Reversal', value: reversalSummary(request, userName) },
              {
                label: 'Evidence',
                value: (
                  <span className="space-x-3">
                    {request.alert_id && (
                      <Link
                        to={`/alerts/${request.alert_id}`}
                        className="text-cyan-700 hover:underline"
                      >
                        Alert #{request.alert_id}
                      </Link>
                    )}
                    {request.incident_id && (
                      <Link
                        to={`/incidents/${request.incident_id}`}
                        className="text-cyan-700 hover:underline"
                      >
                        Incident #{request.incident_id}
                      </Link>
                    )}
                    {!request.alert_id && !request.incident_id && 'None linked'}
                  </span>
                ),
              },
            ]}
          />
          <div className="mt-4">
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Reason</h3>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{request.reason}</p>
          </div>
        </Panel>

        <Panel title="Helper results" flush>
          <DataTable
            caption="Results reported by the firewall helper"
            rows={request.results ?? []}
            rowKey={(r) => r.id}
            empty={
              <p className="p-4 text-sm text-slate-500">The helper has not reported any action.</p>
            }
            columns={[
              { key: 'op', header: 'Operation', render: (r) => humanize(r.operation) },
              {
                key: 'ok',
                header: 'Result',
                render: (r) =>
                  r.success ? (
                    <StatusBadge tone="success" label="Succeeded" />
                  ) : (
                    <span>
                      <StatusBadge tone="danger" label="Failed" />{' '}
                      <span className="text-xs">{r.error_message ?? r.error_code}</span>
                    </span>
                  ),
              },
              { key: 'at', header: 'When', render: (r) => formatDateTime(r.executed_at) },
            ]}
          />
        </Panel>
      </div>

      {decision && (
        <DecisionDialog
          request={request}
          decision={decision}
          onClose={() => setDecision(null)}
          onDone={() => {
            setDecision(null)
            onChanged()
          }}
        />
      )}
    </>
  )
}

function DecisionDialog({
  request,
  decision,
  onClose,
  onDone,
}: {
  request: FirewallRequestOut
  decision: Decision
  onClose: () => void
  onDone: () => void
}) {
  const [note, setNote] = useState('')
  const action = useAction(async () => {
    const trimmed = note.trim()
    if (decision === 'approve') {
      return approveFirewallRequest(request.id, {
        confirm_target: request.target,
        note: trimmed || null,
      })
    }
    if (decision === 'reject') return rejectFirewallRequest(request.id, { note: trimmed })
    return revokeFirewallRequest(request.id, { note: trimmed || null })
  })

  async function confirm() {
    if (await action.run()) onDone()
  }

  const titles: Record<Decision, string> = {
    approve: `Approve blocking ${request.target}?`,
    reject: `Reject the request to block ${request.target}?`,
    revoke: `Revoke the block on ${request.target}?`,
  }

  return (
    <ConfirmDialog
      title={titles[decision]}
      confirmLabel={
        decision === 'approve' ? 'Approve block' : decision === 'reject' ? 'Reject' : 'Revoke'
      }
      tone={decision === 'approve' ? 'danger' : 'primary'}
      requireText={decision === 'approve' ? request.target : undefined}
      confirmDisabled={decision === 'reject' && note.trim().length < 3}
      pending={action.pending}
      error={action.error}
      onConfirm={confirm}
      onCancel={onClose}
    >
      {decision === 'approve' && (
        <>
          <p>
            You are approving a temporary block of{' '}
            <strong className="font-mono">{request.target}</strong> for{' '}
            {formatDuration(request.duration_seconds)}. Check the evidence first: an alert is a
            model prediction, not proof.
          </p>
          <p className="text-xs text-slate-500">
            Until the Phase 7 helper exists, approval is recorded but no rule is applied.
          </p>
        </>
      )}
      {decision === 'revoke' && (
        <p>The request will be closed. Any applied rule is removed by the helper (Phase 7).</p>
      )}
      <Field
        label={decision === 'reject' ? 'Reason for rejecting (required)' : 'Note (optional)'}
        hint={decision === 'reject' ? 'At least 3 characters' : undefined}
      >
        {(props) => (
          <textarea
            {...props}
            rows={2}
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        )}
      </Field>
    </ConfirmDialog>
  )
}
