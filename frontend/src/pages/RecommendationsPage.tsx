import { Link } from 'react-router'

import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { useApiResource } from '../hooks/useApiResource'
import type { Tone } from '../lib/labels'
import { listRecommendationRules } from '../services/api/recommendations'
import type { RuleOut } from '../types/api'

const KIND_LABEL: Record<RuleOut['kind'], { label: string; tone: Tone; help: string }> = {
  investigate: { label: 'Investigate', tone: 'info', help: 'look at more data' },
  harden: { label: 'Harden', tone: 'warning', help: 'change a configuration' },
  contain: { label: 'Contain', tone: 'danger', help: 'limit or block traffic' },
}

/** Rule text uses placeholders such as {src}; show them as readable markers. */
function template(text: string): string {
  return text.replace(/\{(\w+)\}/g, (_, name: string) => `‹${name}›`)
}

export function RecommendationsPage() {
  const { state, reload } = useApiResource(listRecommendationRules)
  return (
    <>
      <PageHeader
        title="Recommendations"
        description="The transparent rules that suggest defensive actions for alerts. Each alert's page shows the recommendations made for it and the evidence they were based on."
      />
      <div className="mb-6 space-y-3">
        <Notice title="Suggestions, not verdicts">
          An alert is a model prediction, not proof of an attack. A rule's action is suggested only
          when all the evidence it needs is recorded; otherwise the alert gets an “investigate
          further” recommendation that names what is missing. Nothing here blocks traffic: a block
          always needs an administrator-approved firewall request.
        </Notice>
        <p className="text-sm text-slate-600">
          Kinds:{' '}
          {Object.values(KIND_LABEL)
            .map((k) => `${k.label} = ${k.help}`)
            .join('; ')}
          . Open an{' '}
          <Link to="/alerts" className="text-cyan-700 hover:underline">
            alert
          </Link>{' '}
          to see its recommendations.
        </p>
      </div>

      {state.status === 'loading' && <LoadingState label="Loading rules…" />}
      {state.status === 'error' && (
        <ErrorState title="Rules unavailable" error={state.error} onRetry={reload} />
      )}
      {state.status === 'success' && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {state.data.map((rule) => (
            <RuleCard key={rule.rule_id} rule={rule} />
          ))}
        </div>
      )}
    </>
  )
}

function RuleCard({ rule }: { rule: RuleOut }) {
  const kind = KIND_LABEL[rule.kind]
  const appliesTo = rule.heuristic
    ? 'Heuristic over stored alerts (not a model category)'
    : rule.categories.length > 0
      ? rule.categories.join(', ')
      : rule.rule_id === 'fallback.investigate'
        ? 'Any alert where another rule lacked evidence'
        : 'Categories without a specific rule'
  return (
    <Panel
      title={rule.rule_id}
      description={`version ${rule.version} · applies to: ${appliesTo}`}
      actions={
        <>
          <StatusBadge tone={kind.tone} label={kind.label} />
          {rule.requires_human_approval && <StatusBadge tone="warning" label="Needs approval" />}
        </>
      }
    >
      <dl className="space-y-2 text-sm">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Action</dt>
          <dd className="text-slate-900">{template(rule.action)}</dd>
        </div>
        {rule.reason && (
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Reason</dt>
            <dd className="text-slate-700">{template(rule.reason)}</dd>
          </div>
        )}
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Required evidence
          </dt>
          <dd className="text-slate-700">
            {rule.required_evidence.length === 0 ? (
              'None (always safe to suggest)'
            ) : (
              <ul className="list-disc pl-5">
                {rule.required_evidence.map((e) => (
                  <li key={e.name}>{e.description}</li>
                ))}
              </ul>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Limitations
          </dt>
          <dd className="text-xs text-slate-600">{rule.limitations}</dd>
        </div>
      </dl>
    </Panel>
  )
}
