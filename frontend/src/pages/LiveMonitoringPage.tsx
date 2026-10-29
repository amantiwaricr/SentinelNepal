import { RefreshCw } from 'lucide-react'
import { useCallback, useState } from 'react'

import { useCurrentUser } from '../auth/AuthContext'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DataTable } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { KeyValueList } from '../components/KeyValueList'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { SourceTag } from '../components/SourceTag'
import { StatusBadge } from '../components/StatusBadge'
import { ALERT_EVENTS, useLiveConnection, useRefreshOn } from '../events/liveEventsContext'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { usePolling } from '../hooks/usePolling'
import {
  formatBytes,
  formatCount,
  formatDateTime,
  formatEndpoint,
  formatScore,
} from '../lib/format'
import {
  getLiveStatus,
  listCollectors,
  listRecentFlows,
  setCollectorMode,
} from '../services/api/live'
import type { CollectorOut, LiveStatusOut, RecentFlowOut } from '../types/api'

// Collectors going offline sends no notification (the collector is the one that stopped),
// so status is also re-read on a timer.
const STATUS_POLL_MS = 15_000
const FLOW_EVENTS = ['flows.observed', 'resync', ...ALERT_EVENTS]

export function LiveMonitoringPage() {
  const connected = useLiveConnection()
  const status = useApiResource(getLiveStatus)
  const collectors = useApiResource(listCollectors)
  const flows = useApiResource(listRecentFlows)

  const { reload: reloadStatus } = status
  const { reload: reloadCollectors } = collectors
  const { reload: reloadFlows } = flows

  const pollStatus = useCallback(() => {
    reloadStatus({ quiet: true })
    reloadCollectors({ quiet: true })
  }, [reloadStatus, reloadCollectors])
  const refresh = useCallback(() => {
    pollStatus()
    reloadFlows({ quiet: true })
  }, [pollStatus, reloadFlows])

  useRefreshOn(FLOW_EVENTS, refresh)
  usePolling(pollStatus, STATUS_POLL_MS, true)

  return (
    <>
      <PageHeader
        title="Live Monitoring"
        description="Flows built by TShark collectors in the authorised lab, and whether the model may score them."
        actions={
          <>
            <StatusBadge
              tone={connected ? 'success' : 'warning'}
              label={connected ? 'Live updates on' : 'Live updates reconnecting…'}
            />
            <Button onClick={refresh}>
              <RefreshCw aria-hidden="true" className="h-4 w-4" />
              Refresh
            </Button>
          </>
        }
      />
      <div className="mb-4">
        <Notice title="Model scores on lab traffic are suspicions, not proof">
          The model was trained on the UNSW-NB15 dataset; lab flows are built differently (some
          features are approximations), so its scores here are uncalibrated and unvalidated. A live
          alert means the model found a flow suspicious, not that an attack happened.
        </Notice>
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Live scoring gate">
          {status.state.status === 'loading' && <LoadingState label="Loading live status…" />}
          {status.state.status === 'error' && (
            <ErrorState
              title="Live status unavailable"
              error={status.state.error}
              onRetry={status.reload}
            />
          )}
          {status.state.status === 'success' && <GateSummary status={status.state.data} />}
        </Panel>
        <Panel title="Collectors" flush>
          {collectors.state.status === 'loading' && <LoadingState label="Loading collectors…" />}
          {collectors.state.status === 'error' && (
            <div className="p-4">
              <ErrorState
                title="Collectors unavailable"
                error={collectors.state.error}
                onRetry={collectors.reload}
              />
            </div>
          )}
          {collectors.state.status === 'success' && (
            <CollectorList
              collectors={collectors.state.data}
              modelReady={status.state.status === 'success' && status.state.data.model_ready}
              onChanged={refresh}
            />
          )}
        </Panel>
      </div>
      <Panel
        title="Recent flows"
        description="The latest flows received, newest first (kept in memory by the backend, not stored)."
        className="mt-6"
        flush
      >
        {flows.state.status === 'loading' && <LoadingState label="Loading flows…" />}
        {flows.state.status === 'error' && (
          <div className="p-4">
            <ErrorState
              title="Flows unavailable"
              error={flows.state.error}
              onRetry={flows.reload}
            />
          </div>
        )}
        {flows.state.status === 'success' && <FlowTable flows={flows.state.data} />}
      </Panel>
    </>
  )
}

function GateSummary({ status }: { status: LiveStatusOut }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge
          tone={status.model_ready ? 'success' : 'neutral'}
          label={status.model_ready ? 'Live scoring allowed' : 'Live scoring off'}
        />
        {status.model_ready && status.collectors_scoring === 0 && (
          <span className="text-xs text-slate-500">No collector is in inference mode.</span>
        )}
      </div>
      <p className="text-sm text-slate-700">{status.reason}</p>
      <KeyValueList
        items={[
          {
            label: 'Live model',
            value: status.model
              ? `${status.model.name} ${status.model.version}`
              : `None (needs an active ${status.live_model_profile} model)`,
          },
          {
            label: 'Approved for live use',
            value: status.approved ? 'Yes (by an administrator)' : 'No',
          },
          { label: 'Alert threshold', value: formatScore(status.alert_threshold) },
          {
            label: 'Collectors',
            value: `${status.collectors_online} of ${status.collectors_total} online, ${status.collectors_scoring} scoring`,
          },
          { label: 'Batches waiting', value: formatCount(status.queue_batches) },
        ]}
      />
      {status.unavailable_features.length > 0 && (
        <Notice tone="warning" title="Features live traffic cannot supply">
          <span className="font-mono">{status.unavailable_features.join(', ')}</span>
        </Notice>
      )}
      {status.approximate_features.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-medium text-cyan-700">
            Approximated features ({status.approximate_features.length})
          </summary>
          <p className="mt-1 text-xs text-slate-600">
            Computed from TShark fields with a documented formula that may differ from the dataset’s
            Argus/Bro tools (see docs/feature-mapping.md):{' '}
            <span className="font-mono">{status.approximate_features.join(', ')}</span>
          </p>
        </details>
      )}
    </div>
  )
}

function stat(collector: CollectorOut, name: string): string {
  const value = collector.heartbeat_stats[name]
  return typeof value === 'number' ? formatCount(value) : '—'
}

function CollectorList({
  collectors,
  modelReady,
  onChanged,
}: {
  collectors: CollectorOut[]
  modelReady: boolean
  onChanged: () => void
}) {
  const user = useCurrentUser()
  const [switching, setSwitching] = useState<CollectorOut | null>(null)

  if (collectors.length === 0) {
    return (
      <EmptyState title="No collectors registered">
        An operator registers one with{' '}
        <code className="font-mono">python -m app.cli create-collector --name lab-sensor</code> and
        gives its token to the collector (see docs/lab-runbook.md).
      </EmptyState>
    )
  }

  return (
    <>
      <ul className="divide-y divide-slate-200">
        {collectors.map((c) => (
          <li key={c.id} className="space-y-2 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-slate-900">{c.name}</span>
              <StatusBadge
                tone={c.online ? 'success' : 'danger'}
                label={c.online ? 'Online' : 'Offline'}
              />
              <StatusBadge
                tone={c.mode === 'inference' ? 'info' : 'neutral'}
                label={c.mode === 'inference' ? 'Inference mode' : 'Observation mode'}
              />
              {user.role === 'admin' && (
                <Button size="sm" className="ml-auto" onClick={() => setSwitching(c)}>
                  {c.mode === 'inference' ? 'Switch to observation…' : 'Switch to inference…'}
                </Button>
              )}
            </div>
            <p className="text-xs text-slate-500">
              Last heartbeat {formatDateTime(c.last_heartbeat_at)}
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
              <Counter label="Records received" value={formatCount(c.records_received)} />
              <Counter label="Rejected" value={formatCount(c.records_rejected)} />
              <Counter label="Dropped (queue full)" value={formatCount(c.records_dropped)} />
              <Counter label="Processed" value={formatCount(c.records_processed)} />
              <Counter label="Alerts created" value={formatCount(c.alerts_created)} />
              <Counter label="Packets read" value={stat(c, 'packets')} />
              <Counter label="Open flows" value={stat(c, 'open_flows')} />
              <Counter label="Unreadable captures" value={stat(c, 'capture_files_failed')} />
              <Counter label="Send failures" value={stat(c, 'send_failures')} />
              <Counter label="Waiting to send" value={stat(c, 'send_buffer')} />
            </dl>
            {c.last_error && (
              <Notice tone="warning" title="Last reported problem">
                {c.last_error}
              </Notice>
            )}
          </li>
        ))}
      </ul>
      {switching && (
        <ModeDialog
          collector={switching}
          modelReady={modelReady}
          onClose={() => setSwitching(null)}
          onSaved={() => {
            setSwitching(null)
            onChanged()
          }}
        />
      )}
    </>
  )
}

function Counter({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium tabular-nums text-slate-900">{value}</dd>
    </div>
  )
}

function ModeDialog({
  collector,
  modelReady,
  onClose,
  onSaved,
}: {
  collector: CollectorOut
  modelReady: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const target = collector.mode === 'inference' ? 'observation' : 'inference'
  const action = useAction(() => setCollectorMode(collector.id, target))

  return (
    <ConfirmDialog
      title={`Switch ${collector.name} to ${target} mode?`}
      confirmLabel={target === 'inference' ? 'Start scoring' : 'Stop scoring'}
      pending={action.pending}
      error={action.error}
      onConfirm={async () => {
        if (await action.run()) onSaved()
      }}
      onCancel={onClose}
    >
      {target === 'inference' ? (
        <>
          <p>
            The live model will score this collector’s flows and may raise alerts. Alerts are
            suspicions for an analyst to review; nothing is blocked automatically.
          </p>
          {!modelReady && (
            <p className="text-amber-800">
              The live gate is closed, so the server will refuse this until an administrator
              approves a compatible active model.
            </p>
          )}
        </>
      ) : (
        <p>Flows will still be shown, but no longer scored.</p>
      )}
    </ConfirmDialog>
  )
}

function FlowTable({ flows }: { flows: RecentFlowOut[] }) {
  return (
    <DataTable
      caption="Recent flows"
      rows={flows}
      rowKey={(f) =>
        `${f.collector_id}-${f.observed_at}-${f.src_ip}-${f.src_port}-${f.dst_ip}-${f.dst_port}`
      }
      empty={
        <EmptyState title="No flows received yet">
          Start a collector in the lab and generate some traffic (see docs/lab-runbook.md).
        </EmptyState>
      }
      columns={[
        { key: 'time', header: 'Received', render: (f) => formatDateTime(f.observed_at) },
        { key: 'source', header: 'Source', render: (f) => <SourceTag source={f.source} /> },
        {
          key: 'from',
          header: 'Originator',
          className: 'font-mono text-xs',
          render: (f) => formatEndpoint(f.src_ip, f.src_port),
        },
        {
          key: 'to',
          header: 'Responder',
          className: 'font-mono text-xs',
          render: (f) => formatEndpoint(f.dst_ip, f.dst_port),
        },
        {
          key: 'proto',
          header: 'Protocol / service',
          render: (f) => `${f.proto ?? '—'} / ${f.service ?? '—'}`,
        },
        { key: 'state', header: 'State', render: (f) => f.state ?? '—' },
        {
          key: 'dur',
          header: 'Duration',
          className: 'tabular-nums',
          render: (f) => (f.dur == null ? '—' : `${f.dur.toFixed(3)} s`),
        },
        {
          key: 'pkts',
          header: 'Packets (out/in)',
          className: 'tabular-nums',
          render: (f) => `${f.spkts ?? '—'} / ${f.dpkts ?? '—'}`,
        },
        {
          key: 'bytes',
          header: 'Bytes (out/in)',
          className: 'tabular-nums',
          render: (f) =>
            `${f.sbytes == null ? '—' : formatBytes(f.sbytes)} / ${f.dbytes == null ? '—' : formatBytes(f.dbytes)}`,
        },
        {
          key: 'scored',
          header: 'Scored',
          render: (f) => (
            <StatusBadge
              tone={f.scored ? 'info' : 'neutral'}
              label={f.scored ? 'Scored' : 'Not scored'}
            />
          ),
        },
      ]}
    />
  )
}
