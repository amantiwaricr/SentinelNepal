import { BellRing, BrainCircuit, FolderOpen, ShieldAlert } from 'lucide-react'
import { lazy, Suspense, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ComponentHealthList } from '../components/ComponentHealthList'
import { CountList } from '../components/CountList'
import { DataTable } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { SegmentedControl } from '../components/SegmentedControl'
import { SeverityBadge } from '../components/SeverityBadge'
import { StatCard } from '../components/StatCard'
import { useApiResource } from '../hooks/useApiResource'
import { formatCount, formatDateTime, formatScore, humanize } from '../lib/format'
import { INCIDENT_STATUS_LABELS, INCIDENT_STATUSES, SEVERITIES } from '../lib/labels'
import { getComponents } from '../services/api/health'
import { getDashboard } from '../services/api/investigation'
import type { DashboardOut, DashboardSource, IncidentStatus, Severity } from '../types/api'

// Recharts is large; load the charts separately so other pages do not download it.
const ActivityChart = lazy(() =>
  import('../components/charts/ActivityChart').then((m) => ({ default: m.ActivityChart })),
)
const CategoryChart = lazy(() =>
  import('../components/charts/CategoryChart').then((m) => ({ default: m.CategoryChart })),
)

const ACTIVITY_DAYS = 14 // matches the backend's dashboard window

const SOURCE_OPTIONS: { value: DashboardSource; label: string }[] = [
  { value: 'all', label: 'All sources' },
  { value: 'dataset', label: 'Dataset analysis' },
  { value: 'live', label: 'Live & replay' },
]

const SOURCE_DESCRIPTION: Record<DashboardSource, string> = {
  all: 'Alerts from uploaded dataset files and from live or replayed traffic, combined.',
  dataset:
    'Alerts produced by analysing uploaded UNSW-NB15 files. These describe the dataset, not traffic on this network.',
  live: 'Alerts from live collectors and CSV replays through the live pipeline.',
}

function parseSource(value: string | null): DashboardSource {
  return value === 'dataset' || value === 'live' ? value : 'all'
}

export function DashboardPage() {
  const [params, setParams] = useSearchParams()
  const source = parseSource(params.get('source'))
  const loadDashboard = useCallback(
    (signal: AbortSignal) => getDashboard({ source }, signal),
    [source],
  )
  const { state, reload } = useApiResource(loadDashboard)

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Figures computed by the backend from stored alerts, incidents and analysis runs."
        actions={
          <SegmentedControl
            label="Alert source"
            value={source}
            options={SOURCE_OPTIONS}
            onChange={(value) => setParams(value === 'all' ? {} : { source: value })}
          />
        }
      />
      <div className="mb-4">
        <Notice title={source === 'dataset' ? 'Dataset-analysis results' : undefined}>
          {SOURCE_DESCRIPTION[source]} Alerts are model predictions, not confirmed attacks.
        </Notice>
      </div>

      {state.status === 'loading' && <LoadingState label="Loading dashboard…" />}
      {state.status === 'error' && (
        <ErrorState title="Dashboard unavailable" error={state.error} onRetry={reload} />
      )}
      {state.status === 'success' && <DashboardContent data={state.data} />}
    </>
  )
}

function DashboardContent({ data }: { data: DashboardOut }) {
  const openIncidents =
    (data.incidents_by_status.new ?? 0) + (data.incidents_by_status.under_investigation ?? 0)
  const alertsLink = data.source === 'dataset' ? '/alerts?source=dataset' : '/alerts'
  const topIps = Object.entries(data.top_source_ips).map(([ip, count]) => ({ ip, count }))
  const model = data.active_models[0]

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total alerts" value={formatCount(data.alerts_total)} icon={ShieldAlert} />
        <StatCard
          label="New (unreviewed) alerts"
          value={formatCount(data.alerts_new)}
          icon={BellRing}
          hint={
            <Link
              className="text-cyan-700 hover:underline"
              to={`${alertsLink}${alertsLink.includes('?') ? '&' : '?'}status=new`}
            >
              Review new alerts
            </Link>
          }
        />
        <StatCard
          label="Open incidents"
          value={formatCount(openIncidents)}
          icon={FolderOpen}
          hint="New or under investigation (all sources)"
        />
        <StatCard
          label="Active model"
          value={<span className="text-base">{model ? `${model.name}` : 'None'}</span>}
          icon={BrainCircuit}
          hint={
            model
              ? `${model.feature_profile} · threshold ${model.alert_threshold == null ? 'default decision' : formatScore(model.alert_threshold)}`
              : 'Register a model to analyse uploads'
          }
        />
      </div>

      {data.alerts_total === 0 && (
        <Notice title="No alerts yet">
          {data.source === 'live'
            ? 'No live or replayed alerts exist. Live monitoring is added in Phase 6.'
            : 'Upload a UNSW-NB15 CSV on the Dataset Analysis page to produce dataset alerts.'}
        </Notice>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel
          title="Alert activity"
          description={`Alerts created per day, last ${ACTIVITY_DAYS} days (UTC)`}
          className="xl:col-span-2"
        >
          <Suspense fallback={<LoadingState label="Loading chart…" />}>
            <ActivityChart
              points={data.alert_activity_by_day}
              generatedAt={data.generated_at}
              days={ACTIVITY_DAYS}
            />
          </Suspense>
        </Panel>
        <Panel
          title="Alerts by severity"
          description="Severity follows a fixed category/score rule"
        >
          <CountList
            counts={data.alerts_by_severity}
            order={SEVERITIES}
            renderLabel={(key) => <SeverityBadge severity={key as Severity} />}
          />
          <div className="mt-4 border-t border-slate-100 pt-3">
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
              By review status
            </h3>
            <CountList counts={data.alerts_by_status} renderLabel={humanize} />
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel
          title="Alerts by predicted category"
          description="The model's suspected category; several categories are unreliable (see Model Evaluation)"
          className="xl:col-span-2"
        >
          {Object.keys(data.alerts_by_category).length === 0 ? (
            <EmptyState title="No alerts to categorise" />
          ) : (
            <Suspense fallback={<LoadingState label="Loading chart…" />}>
              <CategoryChart counts={data.alerts_by_category} />
            </Suspense>
          )}
        </Panel>
        <Panel title="Frequent source IPs" description="Top 10 by alert count" flush>
          <DataTable
            caption="Most frequent source IP addresses"
            rows={topIps}
            rowKey={(row) => row.ip}
            empty={<EmptyState title="No source addresses recorded" />}
            columns={[
              {
                key: 'ip',
                header: 'Source IP',
                render: (row) => (
                  <Link
                    to={`/ips?ip=${encodeURIComponent(row.ip)}`}
                    className="font-mono text-cyan-700 hover:underline"
                  >
                    {row.ip}
                  </Link>
                ),
              },
              {
                key: 'count',
                header: 'Alerts',
                className: 'text-right tabular-nums',
                render: (row) => formatCount(row.count),
              },
            ]}
          />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Panel title="Incidents by status" description="All incidents, any source">
          <CountList
            counts={data.incidents_by_status}
            order={INCIDENT_STATUSES}
            empty="No incidents yet"
            renderLabel={(key) => (
              <Link to={`/incidents?status=${key}`} className="text-cyan-700 hover:underline">
                {INCIDENT_STATUS_LABELS[key as IncidentStatus]}
              </Link>
            )}
          />
        </Panel>
        <Panel title="Dataset analysis runs">
          <CountList
            counts={data.analysis_runs_by_status}
            renderLabel={humanize}
            empty="No files analysed yet"
          />
          <Link to="/datasets" className="mt-3 inline-block text-sm text-cyan-700 hover:underline">
            Upload or view runs
          </Link>
        </Panel>
        <HealthPanel />
      </div>

      <p className="text-xs text-slate-500">Generated {formatDateTime(data.generated_at)}</p>
    </div>
  )
}

function HealthPanel() {
  const { state, reload } = useApiResource(getComponents)
  return (
    <Panel
      title="Collector and model health"
      actions={
        <Link to="/system" className="text-sm text-cyan-700 hover:underline">
          Details
        </Link>
      }
    >
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && (
        <ErrorState title="Health unavailable" error={state.error} onRetry={reload} />
      )}
      {state.status === 'success' && <ComponentHealthList components={state.data.components} />}
    </Panel>
  )
}
