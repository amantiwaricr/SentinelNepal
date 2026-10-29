import { Upload } from 'lucide-react'
import { useCallback, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useUserName } from '../auth/userDirectoryContext'
import { Button } from '../components/Button'
import { CountList } from '../components/CountList'
import { DataTable } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { FormError } from '../components/FormError'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { usePolling } from '../hooks/usePolling'
import { formatBytes, formatCount, formatDateTime, humanize } from '../lib/format'
import { ANALYSIS_STATUS_TONE } from '../lib/labels'
import { positiveInt } from '../lib/params'
import { listAnalysisRuns, uploadDataset } from '../services/api/datasets'
import type { AnalysisRunOut } from '../types/api'

const PAGE_SIZE = 20
const POLL_MS = 3000

interface RunSummary {
  alert_rule?: string
  predicted_class_counts?: Record<string, number>
  alerts_by_category?: Record<string, number>
  alerts_suppressed_over_cap?: number
  rejection_reasons?: Record<string, number>
  rows_with_ip_metadata?: number
  note?: string
}

export function DatasetAnalysisPage() {
  const userName = useUserName()
  const [params, setParams] = useSearchParams()
  const page = positiveInt(params.get('page')) ?? 1
  const load = useCallback(
    (signal: AbortSignal) => listAnalysisRuns({ page, page_size: PAGE_SIZE }, signal),
    [page],
  )
  const { state, reload } = useApiResource(load)
  const busy =
    state.status === 'success' &&
    state.data.items.some((r) => r.status === 'queued' || r.status === 'running')
  const refresh = useCallback(() => reload({ quiet: true }), [reload])
  // REST stays the source of truth: while a run is in progress, re-read its status.
  usePolling(refresh, POLL_MS, busy)

  return (
    <>
      <PageHeader
        title="Dataset Analysis"
        description="Score an uploaded UNSW-NB15-format CSV with the active dataset model. Results are labelled as dataset alerts, never as live traffic."
      />
      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <UploadPanel onUploaded={() => (page === 1 ? refresh() : setParams({}))} />
        <div className="xl:col-span-2">
          <Notice>
            The file is stored under a server-generated name, analysed in the background, and never
            used for training. Label columns in the file are ignored: the model's predictions are
            not compared with them here (see Model Evaluation for measured accuracy).
          </Notice>
        </div>
      </div>

      <Panel title="Analysis runs" flush>
        {state.status === 'loading' && <LoadingState label="Loading runs…" />}
        {state.status === 'error' && (
          <div className="p-4">
            <ErrorState title="Runs unavailable" error={state.error} onRetry={reload} />
          </div>
        )}
        {state.status === 'success' && (
          <>
            <DataTable
              caption="Dataset analysis runs"
              rows={state.data.items}
              rowKey={(r) => r.id}
              empty={<EmptyState title="No files analysed yet" />}
              columns={[
                {
                  key: 'file',
                  header: 'File',
                  render: (r) => (
                    <div>
                      <div className="font-medium text-slate-900">
                        #{r.id} {r.original_filename}
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatBytes(r.size_bytes)} · {userName(r.uploaded_by)} ·{' '}
                        {formatDateTime(r.created_at)}
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (r) => (
                    <div className="space-y-1">
                      <StatusBadge
                        tone={ANALYSIS_STATUS_TONE[r.status]}
                        label={humanize(r.status)}
                      />
                      {r.error_message && (
                        <p className="max-w-xs text-xs text-red-700">{r.error_message}</p>
                      )}
                    </div>
                  ),
                },
                {
                  key: 'rows',
                  header: 'Rows (valid / rejected)',
                  className: 'tabular-nums',
                  render: (r) =>
                    `${formatCount(r.rows_total)} (${formatCount(r.rows_valid)} / ${formatCount(r.rows_rejected)})`,
                },
                {
                  key: 'alerts',
                  header: 'Alerts',
                  render: (r) =>
                    r.alerts_created > 0 ? (
                      <Link to={`/alerts?run_id=${r.id}`} className="text-cyan-700 hover:underline">
                        {formatCount(r.alerts_created)} alerts
                      </Link>
                    ) : (
                      '0'
                    ),
                },
                { key: 'summary', header: 'Summary', render: (r) => <RunSummaryDetails run={r} /> },
              ]}
            />
            {state.data.total > 0 && (
              <Pagination
                page={state.data.page}
                pageSize={state.data.page_size}
                total={state.data.total}
                onPageChange={(p) => setParams({ page: String(p) })}
              />
            )}
          </>
        )}
      </Panel>
    </>
  )
}

function UploadPanel({ onUploaded }: { onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const action = useAction(uploadDataset)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    if (await action.run(file)) {
      setFile(null)
      if (input.current) input.current.value = ''
      onUploaded()
    }
  }

  return (
    <Panel title="Upload a CSV">
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label htmlFor="dataset-file" className="mb-1 block text-xs font-medium text-slate-700">
            UNSW-NB15 CSV file
          </label>
          <input
            id="dataset-file"
            ref={input}
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
          />
          <p className="mt-1 text-xs text-slate-500">
            Partitioned (with header) or full-record (no header) format. The server enforces the
            size limit.
          </p>
        </div>
        <FormError error={action.error} />
        <Button type="submit" variant="primary" disabled={!file || action.pending}>
          <Upload aria-hidden="true" className="h-4 w-4" />
          {action.pending ? 'Uploading…' : 'Upload and analyse'}
        </Button>
      </form>
    </Panel>
  )
}

function RunSummaryDetails({ run }: { run: AnalysisRunOut }) {
  const summary = run.summary as RunSummary
  if (run.status !== 'completed') {
    return (
      <span className="text-xs text-slate-500">
        {run.detected_schema ? `Schema: ${run.detected_schema}` : '—'}
      </span>
    )
  }
  return (
    <details className="text-xs">
      <summary className="cursor-pointer text-cyan-700">Details</summary>
      <div className="mt-2 w-72 space-y-3 text-slate-700">
        {summary.alert_rule && <p>Alert rule: {summary.alert_rule}</p>}
        {run.detected_schema && <p>Detected format: {run.detected_schema}</p>}
        {summary.predicted_class_counts && (
          <div>
            <p className="mb-1 font-medium">Predicted classes (all valid rows)</p>
            <CountList counts={summary.predicted_class_counts} />
          </div>
        )}
        {summary.rejection_reasons && Object.keys(summary.rejection_reasons).length > 0 && (
          <div>
            <p className="mb-1 font-medium">Rejection reasons</p>
            <CountList counts={summary.rejection_reasons} />
          </div>
        )}
        {(summary.alerts_suppressed_over_cap ?? 0) > 0 && (
          <p className="text-amber-800">
            {formatCount(summary.alerts_suppressed_over_cap ?? 0)} alerts not stored (per-run cap
            reached)
          </p>
        )}
        {summary.note && <p className="text-slate-500">{summary.note}</p>}
      </div>
    </details>
  )
}
