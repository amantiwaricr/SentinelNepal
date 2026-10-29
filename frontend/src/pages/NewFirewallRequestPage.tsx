import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { Button } from '../components/Button'
import { FormError } from '../components/FormError'
import { Field } from '../components/FormField'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { useAction } from '../hooks/useAction'
import { formatDuration } from '../lib/format'
import { positiveInt, text } from '../lib/params'
import { createFirewallRequest } from '../services/api/firewall'

const DURATIONS = [300, 900, 1800, 3600]
const MIN_REASON = 10

export function NewFirewallRequestPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [target, setTarget] = useState(text(params.get('target')) ?? '')
  const [duration, setDuration] = useState(900)
  const [reason, setReason] = useState('')
  const [alertId, setAlertId] = useState(params.get('alert_id') ?? '')
  const [incidentId, setIncidentId] = useState(params.get('incident_id') ?? '')
  const [dryRun, setDryRun] = useState(false)
  const action = useAction(createFirewallRequest)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const created = await action.run({
      target: target.trim(),
      duration_seconds: duration,
      reason: reason.trim(),
      alert_id: positiveInt(alertId.trim()) ?? null,
      incident_id: positiveInt(incidentId.trim()) ?? null,
      dry_run: dryRun,
    })
    if (created) navigate(`/firewall/${created.id}`)
  }

  return (
    <>
      <PageHeader
        title="Request a temporary block"
        description="Creates a pending request. An administrator must approve it (by default a different administrator from the requester)."
      />
      <div className="max-w-2xl space-y-4">
        <Notice tone="warning">
          Request a block only with supporting evidence. Alerts are model predictions and can be
          wrong; blocking a legitimate host disrupts the lab. Protected networks (such as the lab's
          management range) are always refused.
        </Notice>
        <Panel>
          <form onSubmit={submit} className="space-y-4">
            <Field
              label="Target IP or CIDR"
              hint="A single address, or a network no broader than /24 (IPv4) or /64 (IPv6)"
            >
              {(props) => (
                <input
                  {...props}
                  required
                  spellCheck={false}
                  className={`${props.className} font-mono`}
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                />
              )}
            </Field>
            <Field label="Duration">
              {(props) => (
                <select
                  {...props}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                >
                  {DURATIONS.map((d) => (
                    <option key={d} value={d}>
                      {formatDuration(d)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field
              label="Reason"
              hint={`Why this block is justified, citing evidence (at least ${MIN_REASON} characters)`}
            >
              {(props) => (
                <textarea
                  {...props}
                  required
                  rows={4}
                  maxLength={1000}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              )}
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Related alert ID (optional)">
                {(props) => (
                  <input
                    {...props}
                    inputMode="numeric"
                    value={alertId}
                    onChange={(e) => setAlertId(e.target.value)}
                  />
                )}
              </Field>
              <Field label="Related incident ID (optional)">
                {(props) => (
                  <input
                    {...props}
                    inputMode="numeric"
                    value={incidentId}
                    onChange={(e) => setIncidentId(e.target.value)}
                  />
                )}
              </Field>
            </div>
            <label className="flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="mt-0.5 rounded border-slate-300 text-cyan-700 focus:ring-cyan-600"
              />
              <span>Dry run: the helper will validate the rule without applying it (Phase 7).</span>
            </label>
            <FormError error={action.error} />
            <div className="flex gap-2">
              <Button
                type="submit"
                variant="primary"
                disabled={action.pending || !target.trim() || reason.trim().length < MIN_REASON}
              >
                {action.pending ? 'Submitting…' : 'Submit for approval'}
              </Button>
              <Button onClick={() => navigate(-1)}>Cancel</Button>
            </div>
          </form>
        </Panel>
      </div>
    </>
  )
}
