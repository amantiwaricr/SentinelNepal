import { Plus } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { useCurrentUser } from '../auth/AuthContext'
import { useUserDirectory, useUserName } from '../auth/userDirectoryContext'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DataTable } from '../components/DataTable'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SelectFilter } from '../components/FilterFields'
import { Field } from '../components/FormField'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { Panel } from '../components/Panel'
import { SeverityBadge } from '../components/SeverityBadge'
import { StatusBadge } from '../components/StatusBadge'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { formatDateTime } from '../lib/format'
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
  INCIDENT_STATUSES,
  SEVERITIES,
} from '../lib/labels'
import { oneOf, positiveInt, toSearchParams } from '../lib/params'
import { createIncident, listIncidents } from '../services/api/incidents'
import type { ListIncidentsQuery, Severity } from '../types/api'

const PAGE_SIZE = 25

export function IncidentsPage() {
  const [params, setParams] = useSearchParams()
  const me = useCurrentUser()
  const { users } = useUserDirectory()
  const userName = useUserName()
  const [creating, setCreating] = useState(false)

  const query: ListIncidentsQuery = {
    status: oneOf(params.get('status'), INCIDENT_STATUSES),
    severity: oneOf(params.get('severity'), SEVERITIES),
    assigned_to: positiveInt(params.get('assigned_to')),
    page: positiveInt(params.get('page')) ?? 1,
    page_size: PAGE_SIZE,
  }
  const queryKey = toSearchParams(query).toString()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- queryKey captures every field of query
  const load = useCallback((signal: AbortSignal) => listIncidents(query, signal), [queryKey])
  const { state, reload } = useApiResource(load)

  function setFilter(key: string, value: string | number) {
    const next = new URLSearchParams(params)
    if (value === '') next.delete(key)
    else next.set(key, String(value))
    if (key !== 'page') next.delete('page')
    setParams(next)
  }

  return (
    <>
      <PageHeader
        title="Incidents"
        description="Investigations opened by analysts. An incident groups alerts and notes; its status records the analyst's conclusion."
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" className="h-4 w-4" />
            New incident
          </Button>
        }
      />

      <Panel className="mb-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <SelectFilter
            label="Status"
            value={query.status ?? ''}
            onChange={(v) => setFilter('status', v)}
            options={INCIDENT_STATUSES.map((s) => [s, INCIDENT_STATUS_LABELS[s]])}
          />
          <SelectFilter
            label="Severity"
            value={query.severity ?? ''}
            onChange={(v) => setFilter('severity', v)}
            options={SEVERITIES.map((s) => [s, s.charAt(0).toUpperCase() + s.slice(1)])}
          />
          <SelectFilter
            label="Assigned to"
            value={query.assigned_to ? String(query.assigned_to) : ''}
            onChange={(v) => setFilter('assigned_to', v)}
            options={[
              [String(me.id), `Me (${me.username})`],
              ...users
                .filter((u) => u.id !== me.id && u.is_active)
                .map((u): [string, string] => [String(u.id), u.username]),
            ]}
          />
        </div>
      </Panel>

      <Panel flush>
        {state.status === 'loading' && <LoadingState label="Loading incidents…" />}
        {state.status === 'error' && (
          <div className="p-4">
            <ErrorState title="Incidents unavailable" error={state.error} onRetry={reload} />
          </div>
        )}
        {state.status === 'success' && (
          <>
            <DataTable
              caption="Incidents"
              rows={state.data.items}
              rowKey={(i) => i.id}
              empty={
                <EmptyState title="No incidents found">
                  Open an incident from an alert, or with “New incident”.
                </EmptyState>
              }
              columns={[
                {
                  key: 'title',
                  header: 'Incident',
                  render: (i) => (
                    <Link
                      to={`/incidents/${i.id}`}
                      className="font-medium text-cyan-700 hover:underline"
                    >
                      #{i.id} {i.title}
                    </Link>
                  ),
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (i) => (
                    <StatusBadge
                      tone={INCIDENT_STATUS_TONE[i.status]}
                      label={INCIDENT_STATUS_LABELS[i.status]}
                    />
                  ),
                },
                {
                  key: 'severity',
                  header: 'Severity',
                  render: (i) => <SeverityBadge severity={i.severity} />,
                },
                {
                  key: 'alerts',
                  header: 'Alerts',
                  className: 'tabular-nums',
                  render: (i) => i.alert_count ?? 0,
                },
                { key: 'assignee', header: 'Assigned to', render: (i) => userName(i.assigned_to) },
                {
                  key: 'updated',
                  header: 'Last updated',
                  className: 'whitespace-nowrap',
                  render: (i) => formatDateTime(i.updated_at),
                },
              ]}
            />
            {state.data.total > 0 && (
              <Pagination
                page={state.data.page}
                pageSize={state.data.page_size}
                total={state.data.total}
                onPageChange={(page) => setFilter('page', page)}
              />
            )}
          </>
        )}
      </Panel>

      {creating && <NewIncidentDialog onClose={() => setCreating(false)} />}
    </>
  )
}

function NewIncidentDialog({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const { users } = useUserDirectory()
  const [title, setTitle] = useState('')
  const [severity, setSeverity] = useState<Severity>('medium')
  const [description, setDescription] = useState('')
  const [assignee, setAssignee] = useState('')
  const action = useAction(createIncident)

  async function confirm() {
    const incident = await action.run({
      title: title.trim(),
      severity,
      description: description.trim(),
      assigned_to: assignee ? Number(assignee) : null,
    })
    if (incident) navigate(`/incidents/${incident.id}`)
  }

  return (
    <ConfirmDialog
      title="New incident"
      confirmLabel="Create incident"
      pending={action.pending}
      confirmDisabled={title.trim().length < 3}
      error={action.error}
      onConfirm={confirm}
      onCancel={onClose}
    >
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
      <div className="grid grid-cols-2 gap-3">
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
        <Field label="Assign to">
          {(props) => (
            <select {...props} value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              <option value="">Unassigned</option>
              {users
                .filter((u) => u.is_active)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.username}
                  </option>
                ))}
            </select>
          )}
        </Field>
      </div>
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
