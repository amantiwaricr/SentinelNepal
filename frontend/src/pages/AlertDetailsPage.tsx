import { FolderPlus, Link2, ShieldBan } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { AlertTable } from '../components/AlertTable'
import { AttackScore } from '../components/AttackScore'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DataTable } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { FormError } from '../components/FormError'
import { Field } from '../components/FormField'
import { KeyValueList } from '../components/KeyValueList'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { SeverityBadge } from '../components/SeverityBadge'
import { SourceTag } from '../components/SourceTag'
import { StatusBadge } from '../components/StatusBadge'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { formatDateTime, formatEndpoint, formatScore } from '../lib/format'
import {
  ALERT_STATUS_LABELS,
  ALERT_STATUS_TONE,
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
  SEVERITIES,
} from '../lib/labels'
import { positiveInt } from '../lib/params'
import { getAlert, listAlerts, updateAlertStatus } from '../services/api/alerts'
import { createIncident, linkAlerts, listIncidents } from '../services/api/incidents'
import type { AlertDetail, AlertStatusUpdate, Severity } from '../types/api'

type Evidence = {
  class_scores_top3?: Record<string, number>
  default_decision?: string
  alert_threshold?: number | null
  features?: Record<string, unknown>
  imputed_features?: string[]
  unknown_categories?: Record<string, unknown>
  severity_rule?: string
  note?: string
}

export function AlertDetailsPage() {
  const alertId = positiveInt(useParams().alertId ?? null)
  if (alertId === undefined) {
    return (
      <>
        <PageHeader title="Alert not found" />
        <Link to="/alerts" className="text-sm text-cyan-700 hover:underline">
          Back to alerts
        </Link>
      </>
    )
  }
  return <AlertDetails alertId={alertId} key={alertId} />
}

function AlertDetails({ alertId }: { alertId: number }) {
  const load = useCallback((signal: AbortSignal) => getAlert(alertId, signal), [alertId])
  const { state, reload } = useApiResource(load)

  if (state.status === 'loading') return <LoadingState label="Loading alert…" />
  if (state.status === 'error') {
    return (
      <>
        <PageHeader title={`Alert ${alertId}`} />
        <ErrorState title="Alert unavailable" error={state.error} onRetry={reload} />
      </>
    )
  }
  return <AlertView alert={state.data} onChanged={() => reload({ quiet: true })} />
}

function AlertView({ alert, onChanged }: { alert: AlertDetail; onChanged: () => void }) {
  const evidence = alert.evidence as Evidence
  const threshold = evidence.alert_threshold ?? null
  const [dialog, setDialog] = useState<'incident' | 'link' | null>(null)
  const status = useAction((body: AlertStatusUpdate) => updateAlertStatus(alert.id, body))

  async function setStatus(next: AlertStatusUpdate['status']) {
    if (await status.run({ status: next })) onChanged()
  }

  return (
    <>
      <PageHeader
        title={`Alert ${alert.id}`}
        description={`Suspected ${alert.predicted_category} · created ${formatDateTime(alert.created_at)}`}
        actions={
          <>
            <Button onClick={() => setDialog('incident')}>
              <FolderPlus aria-hidden="true" className="h-4 w-4" />
              New incident
            </Button>
            <Button onClick={() => setDialog('link')}>
              <Link2 aria-hidden="true" className="h-4 w-4" />
              Add to incident
            </Button>
            {alert.src_ip && (
              <Link
                to={`/firewall/new?target=${encodeURIComponent(alert.src_ip)}&alert_id=${alert.id}`}
                className="inline-flex items-center gap-1.5 rounded-md bg-white px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600"
              >
                <ShieldBan aria-hidden="true" className="h-4 w-4" />
                Request block
              </Link>
            )}
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SourceTag source={alert.source} />
        <SeverityBadge severity={alert.severity} />
        <StatusBadge
          tone={ALERT_STATUS_TONE[alert.status]}
          label={ALERT_STATUS_LABELS[alert.status]}
        />
      </div>

      <div className="mb-6">
        <Notice tone="warning" title="Model prediction, not proof">
          This alert means the model scored the record at or above its alert threshold. The score is
          uncalibrated and the category is a suspicion; confirm with other evidence before acting.
        </Notice>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Panel title="Observed connection">
            <KeyValueList
              items={[
                {
                  label: 'Source',
                  value: alert.src_ip ? (
                    <Link
                      to={`/ips?ip=${encodeURIComponent(alert.src_ip)}`}
                      className="font-mono text-cyan-700 hover:underline"
                    >
                      {formatEndpoint(alert.src_ip, alert.src_port)}
                    </Link>
                  ) : (
                    'Not recorded'
                  ),
                },
                {
                  label: 'Destination',
                  value: alert.dst_ip ? (
                    <Link
                      to={`/ips?ip=${encodeURIComponent(alert.dst_ip)}`}
                      className="font-mono text-cyan-700 hover:underline"
                    >
                      {formatEndpoint(alert.dst_ip, alert.dst_port)}
                    </Link>
                  ) : (
                    'Not recorded'
                  ),
                },
                { label: 'Protocol', value: alert.protocol ?? '—' },
                {
                  label: 'Service',
                  value: alert.service && alert.service !== '-' ? alert.service : '—',
                },
                { label: 'Observed at', value: formatDateTime(alert.observed_at) },
                { label: 'Alert created', value: formatDateTime(alert.created_at) },
                {
                  label: 'Origin',
                  value: alert.analysis_run_id ? (
                    <Link
                      to={`/alerts?run_id=${alert.analysis_run_id}`}
                      className="text-cyan-700 hover:underline"
                    >
                      Dataset analysis run #{alert.analysis_run_id}
                    </Link>
                  ) : (
                    alert.source
                  ),
                },
              ]}
            />
          </Panel>

          <Panel title="Model assessment">
            <KeyValueList
              items={[
                { label: 'Suspected category', value: alert.predicted_category },
                {
                  label: 'Attack score (uncalibrated)',
                  value: <AttackScore score={alert.attack_score} threshold={threshold} />,
                },
                {
                  label: 'Alert threshold',
                  value:
                    threshold == null ? 'Default decision (no threshold)' : formatScore(threshold),
                },
                {
                  label: 'Default decision (highest class)',
                  value: evidence.default_decision ?? '—',
                },
                {
                  label: 'Model',
                  value: (
                    <Link to="/model" className="text-cyan-700 hover:underline">
                      {alert.model.name} {alert.model.version} ({alert.model.feature_profile})
                    </Link>
                  ),
                },
                { label: 'Severity rule', value: evidence.severity_rule ?? '—' },
              ]}
            />
            {evidence.class_scores_top3 && (
              <div className="mt-4">
                <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Highest class scores
                </h3>
                <DataTable
                  caption="Highest class scores from the model"
                  rows={Object.entries(evidence.class_scores_top3)}
                  rowKey={([name]) => name}
                  columns={[
                    { key: 'class', header: 'Class', render: ([name]) => name },
                    {
                      key: 'score',
                      header: 'Score',
                      className: 'font-mono',
                      render: ([, score]) => formatScore(score),
                    },
                  ]}
                />
              </div>
            )}
          </Panel>

          <EvidencePanel evidence={evidence} />
          <RelatedAlerts alert={alert} />
        </div>

        <div className="space-y-6">
          <Panel title="Review status">
            <p className="mb-3 text-sm text-slate-600">
              {alert.status === 'linked'
                ? 'This alert is part of an incident; its status follows the incident.'
                : 'Mark the alert once you have looked at it.'}
            </p>
            <div className="flex flex-wrap gap-2">
              {alert.status !== 'acknowledged' && alert.status !== 'linked' && (
                <Button
                  size="sm"
                  disabled={status.pending}
                  onClick={() => setStatus('acknowledged')}
                >
                  Acknowledge
                </Button>
              )}
              {alert.status !== 'dismissed' && alert.status !== 'linked' && (
                <Button size="sm" disabled={status.pending} onClick={() => setStatus('dismissed')}>
                  Dismiss
                </Button>
              )}
              {(alert.status === 'acknowledged' || alert.status === 'dismissed') && (
                <Button size="sm" disabled={status.pending} onClick={() => setStatus('new')}>
                  Reopen
                </Button>
              )}
            </div>
            <div className="mt-3">
              <FormError error={status.error} />
            </div>
          </Panel>

          <Panel title="Incidents">
            {alert.incidents.length === 0 ? (
              <p className="text-sm text-slate-500">Not linked to any incident.</p>
            ) : (
              <ul className="space-y-2">
                {alert.incidents.map((incident) => (
                  <li key={incident.id} className="flex items-center justify-between gap-2 text-sm">
                    <Link
                      to={`/incidents/${incident.id}`}
                      className="text-cyan-700 hover:underline"
                    >
                      #{incident.id} {incident.title}
                    </Link>
                    <StatusBadge
                      tone={INCIDENT_STATUS_TONE[incident.status]}
                      label={INCIDENT_STATUS_LABELS[incident.status]}
                    />
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Recommendations">
            {alert.recommendations.length === 0 ? (
              <p className="text-sm text-slate-500">
                No recommendations stored for this alert. The recommendation engine is added in
                Phase 5.
              </p>
            ) : (
              <ul className="space-y-3">
                {alert.recommendations.map((r) => (
                  <li key={r.id} className="text-sm">
                    <p className="font-medium text-slate-900">{r.action}</p>
                    <p className="text-slate-600">{r.reason}</p>
                    <p className="mt-1 text-xs text-slate-500">Limitations: {r.limitations}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      {dialog === 'incident' && (
        <CreateIncidentDialog alert={alert} onClose={() => setDialog(null)} />
      )}
      {dialog === 'link' && (
        <LinkIncidentDialog
          alert={alert}
          onClose={() => setDialog(null)}
          onLinked={() => {
            setDialog(null)
            onChanged()
          }}
        />
      )}
    </>
  )
}

function EvidencePanel({ evidence }: { evidence: Evidence }) {
  const features = Object.entries(evidence.features ?? {})
  const imputed = evidence.imputed_features ?? []
  const unknown = Object.entries(evidence.unknown_categories ?? {})
  return (
    <Panel
      title="Evidence"
      description="The feature values the model scored, as stored with the alert"
    >
      {(imputed.length > 0 || unknown.length > 0) && (
        <div className="mb-3 space-y-2">
          {imputed.length > 0 && (
            <Notice tone="warning">
              Missing values filled in by the preprocessing pipeline: {imputed.join(', ')}
            </Notice>
          )}
          {unknown.length > 0 && (
            <Notice tone="warning">
              Values not seen in training (treated as unknown):{' '}
              {unknown.map(([k, v]) => `${k}=${String(v)}`).join(', ')}
            </Notice>
          )}
        </div>
      )}
      {features.length === 0 ? (
        <p className="text-sm text-slate-500">No feature values were stored.</p>
      ) : (
        <details>
          <summary className="cursor-pointer text-sm font-medium text-cyan-700">
            Show {features.length} feature values
          </summary>
          <div className="mt-2 max-h-96 overflow-y-auto">
            <DataTable
              caption="Feature values scored by the model"
              rows={features}
              rowKey={([name]) => name}
              columns={[
                {
                  key: 'name',
                  header: 'Feature',
                  className: 'font-mono text-xs',
                  render: ([n]) => n,
                },
                {
                  key: 'value',
                  header: 'Value',
                  className: 'font-mono text-xs',
                  render: ([, v]) => (v === null ? 'missing' : String(v)),
                },
              ]}
            />
          </div>
        </details>
      )}
    </Panel>
  )
}

function RelatedAlerts({ alert }: { alert: AlertDetail }) {
  const ip = alert.src_ip
  const load = useCallback(
    (signal: AbortSignal) =>
      ip
        ? listAlerts({ src_ip: ip, page_size: 6, sort: '-created_at' }, signal)
        : Promise.resolve(null),
    [ip],
  )
  const { state } = useApiResource(load)
  if (!ip) return null
  const others =
    state.status === 'success' && state.data
      ? state.data.items.filter((a) => a.id !== alert.id).slice(0, 5)
      : []
  return (
    <Panel
      title="Other alerts from this source"
      flush
      actions={
        <Link
          to={`/ips?ip=${encodeURIComponent(ip)}`}
          className="text-sm text-cyan-700 hover:underline"
        >
          Investigate {ip}
        </Link>
      }
    >
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && (
        <p className="p-4 text-sm text-red-700">
          Could not load related alerts: {state.error.message}
        </p>
      )}
      {state.status === 'success' && (
        <AlertTable
          alerts={others}
          caption={`Other alerts with source ${ip}`}
          empty={<EmptyState title="No other alerts from this address" />}
        />
      )}
    </Panel>
  )
}

function CreateIncidentDialog({ alert, onClose }: { alert: AlertDetail; onClose: () => void }) {
  const navigate = useNavigate()
  const [title, setTitle] = useState(
    `Suspected ${alert.predicted_category}${alert.src_ip ? ` from ${alert.src_ip}` : ''}`,
  )
  const [severity, setSeverity] = useState<Severity>(alert.severity)
  const [description, setDescription] = useState('')
  const action = useAction(createIncident)

  async function confirm() {
    const incident = await action.run({
      title: title.trim(),
      severity,
      description: description.trim(),
      alert_ids: [alert.id],
    })
    if (incident) navigate(`/incidents/${incident.id}`)
  }

  return (
    <ConfirmDialog
      title="Open an investigation"
      confirmLabel="Create incident"
      pending={action.pending}
      error={action.error}
      onConfirm={confirm}
      onCancel={onClose}
    >
      <p>
        The incident starts as <strong>New</strong> with alert #{alert.id} linked. Opening an
        incident does not confirm an attack.
      </p>
      <Field label="Title" hint="3–200 characters">
        {(props) => (
          <input
            {...props}
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
          />
        )}
      </Field>
      <Field label="Severity">
        {(props) => (
          <select
            {...props}
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Severity)}
          >
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Description (optional)">
        {(props) => (
          <textarea
            {...props}
            rows={3}
            maxLength={10000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        )}
      </Field>
    </ConfirmDialog>
  )
}

function LinkIncidentDialog({
  alert,
  onClose,
  onLinked,
}: {
  alert: AlertDetail
  onClose: () => void
  onLinked: () => void
}) {
  const load = useCallback((signal: AbortSignal) => listIncidents({ page_size: 100 }, signal), [])
  const { state } = useApiResource(load)
  const linked = new Set(alert.incidents.map((i) => i.id))
  const open =
    state.status === 'success'
      ? state.data.items.filter(
          (i) => !linked.has(i.id) && (i.status === 'new' || i.status === 'under_investigation'),
        )
      : []
  const [choice, setChoice] = useState('')
  const action = useAction(linkAlerts)

  async function confirm() {
    if (choice && (await action.run(Number(choice), [alert.id]))) onLinked()
  }

  return (
    <ConfirmDialog
      title="Add alert to an incident"
      confirmLabel="Add to incident"
      pending={action.pending}
      confirmDisabled={!choice}
      error={action.error}
      onConfirm={confirm}
      onCancel={onClose}
    >
      {state.status === 'loading' && <LoadingState label="Loading open incidents…" />}
      {state.status === 'error' && <FormError error={state.error} />}
      {state.status === 'success' &&
        (open.length === 0 ? (
          <p>There are no open incidents to add this alert to. Create a new incident instead.</p>
        ) : (
          <Field label="Open incident">
            {(props) => (
              <select {...props} value={choice} onChange={(e) => setChoice(e.target.value)}>
                <option value="">Choose an incident…</option>
                {open.map((i) => (
                  <option key={i.id} value={i.id}>
                    #{i.id} {i.title} ({INCIDENT_STATUS_LABELS[i.status]})
                  </option>
                ))}
              </select>
            )}
          </Field>
        ))}
    </ConfirmDialog>
  )
}
