import { Pencil } from 'lucide-react'
import { useCallback, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { useUserDirectory, useUserName } from '../auth/userDirectoryContext'
import { AlertTable } from '../components/AlertTable'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { FormError } from '../components/FormError'
import { Field } from '../components/FormField'
import { KeyValueList } from '../components/KeyValueList'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { SeverityBadge } from '../components/SeverityBadge'
import { StatusBadge } from '../components/StatusBadge'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { formatDateTime, humanize } from '../lib/format'
import { INCIDENT_STATUS_LABELS, INCIDENT_STATUS_TONE, SEVERITIES } from '../lib/labels'
import { positiveInt } from '../lib/params'
import {
  addNote,
  getIncident,
  getIncidentHistory,
  listNotes,
  updateIncident,
} from '../services/api/incidents'
import type {
  AuditLogOut,
  IncidentDetail,
  IncidentStatus,
  IncidentUpdate,
  Severity,
} from '../types/api'

const TRANSITION_HELP: Partial<Record<IncidentStatus, string>> = {
  confirmed:
    'Confirming records your conclusion that malicious activity occurred, based on evidence beyond the model output (for example logs, packet captures or host findings).',
  false_positive: 'Marks the alerts as not reflecting malicious activity.',
  resolved: 'Closes the investigation. It can be reopened later.',
}

const MAX_NOTE = 10000

export function IncidentDetailPage() {
  const incidentId = positiveInt(useParams().incidentId ?? null)
  if (incidentId === undefined) {
    return <PageHeader title="Incident not found" />
  }
  return <IncidentDetails incidentId={incidentId} key={incidentId} />
}

function IncidentDetails({ incidentId }: { incidentId: number }) {
  const load = useCallback((signal: AbortSignal) => getIncident(incidentId, signal), [incidentId])
  const { state, reload } = useApiResource(load)
  // Bumped after each change so the notes and history panels refetch too.
  const [version, setVersion] = useState(0)
  const changed = useCallback(() => {
    reload({ quiet: true })
    setVersion((v) => v + 1)
  }, [reload])

  if (state.status === 'loading') return <LoadingState label="Loading incident…" />
  if (state.status === 'error') {
    return (
      <>
        <PageHeader title={`Incident ${incidentId}`} />
        <ErrorState title="Incident unavailable" error={state.error} onRetry={reload} />
      </>
    )
  }
  const incident = state.data
  return (
    <>
      <PageHeader
        title={`Incident ${incident.id}: ${incident.title}`}
        description={`Opened ${formatDateTime(incident.created_at)} · last updated ${formatDateTime(incident.updated_at)}`}
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <SummaryPanel incident={incident} onChanged={changed} />
          <Panel title={`Linked alerts (${incident.alerts.length})`} flush>
            <AlertTable
              alerts={incident.alerts}
              caption="Alerts linked to this incident"
              empty={
                <EmptyState title="No alerts linked">
                  Link alerts from an alert's page with “Add to incident”.
                </EmptyState>
              }
            />
          </Panel>
          <NotesPanel incidentId={incident.id} version={version} onAdded={changed} />
        </div>
        <div className="space-y-6">
          <WorkflowPanel incident={incident} onChanged={changed} />
          <HistoryPanel incidentId={incident.id} version={version} />
        </div>
      </div>
    </>
  )
}

function SummaryPanel({
  incident,
  onChanged,
}: {
  incident: IncidentDetail
  onChanged: () => void
}) {
  const userName = useUserName()
  const [editing, setEditing] = useState(false)
  return (
    <Panel
      title="Summary"
      actions={
        <Button size="sm" onClick={() => setEditing(true)}>
          <Pencil aria-hidden="true" className="h-3.5 w-3.5" />
          Edit
        </Button>
      }
    >
      <KeyValueList
        items={[
          {
            label: 'Status',
            value: (
              <StatusBadge
                tone={INCIDENT_STATUS_TONE[incident.status]}
                label={INCIDENT_STATUS_LABELS[incident.status]}
              />
            ),
          },
          { label: 'Severity', value: <SeverityBadge severity={incident.severity} /> },
          { label: 'Assigned to', value: userName(incident.assigned_to) },
          { label: 'Opened by', value: userName(incident.created_by) },
          { label: 'Resolved at', value: formatDateTime(incident.resolved_at) },
        ]}
      />
      <div className="mt-4">
        <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Description</h3>
        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">
          {incident.description || <span className="text-slate-400">No description.</span>}
        </p>
      </div>
      {editing && (
        <EditDialog
          incident={incident}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            onChanged()
          }}
        />
      )}
    </Panel>
  )
}

function EditDialog({
  incident,
  onClose,
  onSaved,
}: {
  incident: IncidentDetail
  onClose: () => void
  onSaved: () => void
}) {
  const [title, setTitle] = useState(incident.title)
  const [description, setDescription] = useState(incident.description)
  const action = useAction((body: IncidentUpdate) => updateIncident(incident.id, body))

  async function confirm() {
    const body: IncidentUpdate = {}
    if (title.trim() !== incident.title) body.title = title.trim()
    if (description.trim() !== incident.description) body.description = description.trim()
    if (Object.keys(body).length === 0 || (await action.run(body))) onSaved()
  }

  return (
    <ConfirmDialog
      title="Edit incident"
      confirmLabel="Save"
      pending={action.pending}
      confirmDisabled={title.trim().length < 3}
      error={action.error}
      onConfirm={confirm}
      onCancel={onClose}
    >
      <Field label="Title">
        {(props) => (
          <input
            {...props}
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
          />
        )}
      </Field>
      <Field label="Description">
        {(props) => (
          <textarea
            {...props}
            rows={5}
            maxLength={10000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        )}
      </Field>
    </ConfirmDialog>
  )
}

function WorkflowPanel({
  incident,
  onChanged,
}: {
  incident: IncidentDetail
  onChanged: () => void
}) {
  const { users } = useUserDirectory()
  const action = useAction((body: IncidentUpdate) => updateIncident(incident.id, body))
  const [pendingStatus, setPendingStatus] = useState<IncidentStatus | null>(null)
  const [assignee, setAssignee] = useState(incident.assigned_to ? String(incident.assigned_to) : '')
  const [severity, setSeverity] = useState<Severity>(incident.severity)

  async function save(body: IncidentUpdate) {
    if (await action.run(body)) {
      setPendingStatus(null)
      onChanged()
    }
  }

  function saveAssignment(event: FormEvent) {
    event.preventDefault()
    const changes: IncidentUpdate = {}
    const assignedTo = assignee ? Number(assignee) : null
    if (assignedTo !== incident.assigned_to) changes.assigned_to = assignedTo
    if (severity !== incident.severity) changes.severity = severity
    if (Object.keys(changes).length > 0) void save(changes)
  }

  return (
    <Panel title="Workflow">
      <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Change status</h3>
      {incident.allowed_transitions.length === 0 ? (
        <p className="mt-1 text-sm text-slate-500">No status changes are available.</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {incident.allowed_transitions.map((status) => (
            <Button key={status} size="sm" onClick={() => setPendingStatus(status)}>
              {incident.status === 'resolved' && status === 'under_investigation'
                ? 'Reopen'
                : `Mark ${INCIDENT_STATUS_LABELS[status].toLowerCase()}`}
            </Button>
          ))}
        </div>
      )}

      <form onSubmit={saveAssignment} className="mt-5 space-y-3 border-t border-slate-100 pt-4">
        <Field label="Assigned to">
          {(props) => (
            <select {...props} value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              <option value="">Unassigned</option>
              {users
                .filter((u) => u.is_active || u.id === incident.assigned_to)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.username} ({u.role})
                  </option>
                ))}
            </select>
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
        <Button type="submit" size="sm" variant="primary" disabled={action.pending}>
          Save assignment and severity
        </Button>
      </form>
      {!pendingStatus && (
        <div className="mt-3">
          <FormError error={action.error} />
        </div>
      )}

      {pendingStatus && (
        <ConfirmDialog
          title={`Change status to “${INCIDENT_STATUS_LABELS[pendingStatus]}”?`}
          confirmLabel="Change status"
          tone={pendingStatus === 'confirmed' ? 'danger' : 'primary'}
          pending={action.pending}
          error={action.error}
          onConfirm={() => void save({ status: pendingStatus })}
          onCancel={() => {
            setPendingStatus(null)
            action.clearError()
          }}
        >
          <p>
            From <strong>{INCIDENT_STATUS_LABELS[incident.status]}</strong> to{' '}
            <strong>{INCIDENT_STATUS_LABELS[pendingStatus]}</strong>. The change is recorded in the
            audit log.
          </p>
          {TRANSITION_HELP[pendingStatus] && <p>{TRANSITION_HELP[pendingStatus]}</p>}
        </ConfirmDialog>
      )}
    </Panel>
  )
}

function NotesPanel({
  incidentId,
  version,
  onAdded,
}: {
  incidentId: number
  version: number
  onAdded: () => void
}) {
  const load = useCallback(
    (signal: AbortSignal) => listNotes(incidentId, signal),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- version forces a refetch
    [incidentId, version],
  )
  const { state, reload } = useApiResource(load)
  const [body, setBody] = useState('')
  const action = useAction((text: string) => addNote(incidentId, text))

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!body.trim()) return
    if (await action.run(body.trim())) {
      setBody('')
      onAdded()
    }
  }

  return (
    <Panel title="Investigation notes">
      {state.status === 'loading' && <LoadingState label="Loading notes…" />}
      {state.status === 'error' && (
        <ErrorState title="Notes unavailable" error={state.error} onRetry={reload} />
      )}
      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <p className="text-sm text-slate-500">No notes yet.</p>
        ) : (
          <ol className="space-y-3">
            {state.data.map((note) => (
              <li key={note.id} className="rounded-md border border-slate-200 p-3">
                <p className="text-xs text-slate-500">
                  <span className="font-medium text-slate-700">{note.author_username}</span> ·{' '}
                  {formatDateTime(note.created_at)}
                </p>
                {/* Rendered as text: notes are user input and may contain markup. */}
                <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-800">
                  {note.body}
                </p>
              </li>
            ))}
          </ol>
        ))}
      <form onSubmit={submit} className="mt-4 space-y-2">
        <Field
          label="Add a note"
          hint={`${body.length.toLocaleString()} / ${MAX_NOTE.toLocaleString()} characters`}
        >
          {(props) => (
            <textarea
              {...props}
              rows={3}
              maxLength={MAX_NOTE}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          )}
        </Field>
        <FormError error={action.error} />
        <Button type="submit" variant="primary" size="sm" disabled={action.pending || !body.trim()}>
          {action.pending ? 'Saving…' : 'Add note'}
        </Button>
      </form>
    </Panel>
  )
}

function describeHistory(entry: AuditLogOut): string {
  const details = entry.details as Record<string, unknown>
  const from = details.from
  const to = details.to
  switch (entry.action) {
    case 'incident.created':
      return 'Opened the incident'
    case 'incident.status_changed':
      return `Status ${humanize(String(from))} → ${humanize(String(to))}`
    case 'incident.assigned':
      return to == null ? 'Unassigned the incident' : 'Changed the assignee'
    case 'incident.updated':
      // Free-text values are not in the audit log, only which fields changed.
      return `Edited ${Object.keys(details).join(', ')}`
    case 'incident.alerts_linked': {
      const ids = Array.isArray(details.alert_ids) ? details.alert_ids : []
      return `Linked alert${ids.length === 1 ? '' : 's'} ${ids.map((id) => `#${String(id)}`).join(', ')}`
    }
    case 'incident.note_added':
      return 'Added a note'
    default:
      return humanize(entry.action.replace(/^incident\./, ''))
  }
}

function HistoryPanel({ incidentId, version }: { incidentId: number; version: number }) {
  const load = useCallback(
    (signal: AbortSignal) => getIncidentHistory(incidentId, signal),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- version forces a refetch
    [incidentId, version],
  )
  const { state, reload } = useApiResource(load)
  return (
    <Panel title="History" description="From the audit log">
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && (
        <ErrorState title="History unavailable" error={state.error} onRetry={reload} />
      )}
      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <p className="text-sm text-slate-500">No recorded actions.</p>
        ) : (
          <ol className="space-y-3 border-l border-slate-200 pl-4">
            {state.data.map((entry) => (
              <li key={entry.id} className="text-sm">
                <p className="text-slate-800">{describeHistory(entry)}</p>
                <p className="text-xs text-slate-500">
                  {entry.actor_label ?? entry.actor_type} · {formatDateTime(entry.occurred_at)}
                  {entry.outcome !== 'success' && ` · ${entry.outcome}`}
                </p>
              </li>
            ))}
          </ol>
        ))}
      <p className="mt-3 text-xs text-slate-500">
        <Link to={`/alerts`} className="text-cyan-700 hover:underline">
          Browse alerts
        </Link>{' '}
        to link more evidence.
      </p>
    </Panel>
  )
}
