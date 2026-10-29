import { useState } from 'react'

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
import { StatusBadge } from '../components/StatusBadge'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { formatCount, formatDateTime, formatPercent, formatScore } from '../lib/format'
import { activateModel, listModels } from '../services/api/models'
import type { ModelVersionOut } from '../types/api'

interface SplitMetrics {
  macro_f1: number
  attack_recall: number
  false_positive_rate: number
  per_class_precision: Record<string, number>
  records?: number
}

interface Metrics {
  validation?: SplitMetrics
  test?: SplitMetrics
}

interface ThresholdDetails {
  target_fpr?: number
  selected_on?: string
  chosen?: {
    threshold: number
    false_positive_rate: number
    attack_recall: number
    share_alerted: number
  }
}

function splitRows(metrics: Metrics): [string, SplitMetrics][] {
  const rows: [string, SplitMetrics][] = []
  if (metrics.validation) rows.push(['Validation split', metrics.validation])
  if (metrics.test) rows.push(['Testing file (default decision)', metrics.test])
  return rows
}

export function ModelEvaluationPage() {
  const { state, reload } = useApiResource(listModels)
  return (
    <>
      <PageHeader
        title="Model Evaluation"
        description="Offline results recorded when each model was trained and evaluated on UNSW-NB15."
      />
      <div className="mb-4">
        <Notice title="Dataset results, not live performance">
          These figures come from the UNSW-NB15 dataset (validation split and the separate testing
          file). They do not show how a model performs on this lab's traffic. Attack scores are
          uncalibrated: a score is not a probability.
        </Notice>
      </div>
      {state.status === 'loading' && <LoadingState label="Loading models…" />}
      {state.status === 'error' && (
        <ErrorState title="Models unavailable" error={state.error} onRetry={reload} />
      )}
      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <Panel>
            <EmptyState title="No models registered">
              An operator registers a trained model with{' '}
              <code className="font-mono">python -m app.cli register-model</code>.
            </EmptyState>
          </Panel>
        ) : (
          <div className="space-y-6">
            {[...state.data]
              .sort((a, b) => Number(b.is_active) - Number(a.is_active) || b.id - a.id)
              .map((model) => (
                <ModelCard
                  key={model.id}
                  model={model}
                  onActivated={() => reload({ quiet: true })}
                />
              ))}
          </div>
        ))}
    </>
  )
}

function ModelCard({ model, onActivated }: { model: ModelVersionOut; onActivated: () => void }) {
  const user = useCurrentUser()
  const [confirming, setConfirming] = useState(false)
  const action = useAction(() => activateModel(model.id))
  const metrics = model.metrics as Metrics
  const threshold = (model.threshold_details ?? null) as ThresholdDetails | null
  const precision =
    metrics.test?.per_class_precision ?? metrics.validation?.per_class_precision ?? {}
  const precisionSource = model.precision_source ?? (metrics.test ? 'test' : 'validation')
  // The backend decides which categories are unreliable (precision below its threshold).
  const unreliable = new Set(model.low_precision_categories)

  return (
    <Panel
      title={`${model.name} ${model.version}`}
      description={`${model.model_kind} · feature profile ${model.feature_profile} · registered ${formatDateTime(model.created_at)}`}
      actions={
        <>
          {model.is_active ? (
            <StatusBadge tone="success" label="Active" />
          ) : (
            <StatusBadge tone="neutral" label="Inactive" />
          )}
          <StatusBadge
            tone={model.live_inference_approved ? 'info' : 'neutral'}
            label={
              model.live_inference_approved
                ? 'Live inference approved'
                : 'Not approved for live use'
            }
          />
          {user.role === 'admin' && !model.is_active && (
            <Button size="sm" onClick={() => setConfirming(true)}>
              Activate…
            </Button>
          )}
        </>
      }
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="space-y-4">
          <DataTable
            caption="Evaluation metrics by data split"
            rows={splitRows(metrics)}
            rowKey={([name]) => name}
            empty={
              <p className="text-sm text-slate-500">No metrics were recorded for this model.</p>
            }
            columns={[
              { key: 'split', header: 'Data', render: ([name]) => name },
              { key: 'f1', header: 'Macro-F1', render: ([, m]) => formatPercent(m.macro_f1) },
              {
                key: 'recall',
                header: 'Attack recall',
                render: ([, m]) => formatPercent(m.attack_recall),
              },
              {
                key: 'fpr',
                header: 'False-positive rate',
                render: ([, m]) => formatPercent(m.false_positive_rate),
              },
              {
                key: 'n',
                header: 'Records',
                render: ([, m]) => (m.records != null ? formatCount(m.records) : '—'),
              },
            ]}
          />
          <KeyValueList
            items={[
              {
                label: 'Alert threshold',
                value:
                  model.alert_threshold == null
                    ? 'None: alerts use the default decision'
                    : formatScore(model.alert_threshold),
              },
              {
                label: 'Chosen on',
                value: threshold?.selected_on ?? '—',
              },
              {
                label: 'Target false-positive rate',
                value: formatPercent(threshold?.target_fpr),
              },
              {
                label: 'At threshold (validation)',
                value: threshold?.chosen
                  ? `FPR ${formatPercent(threshold.chosen.false_positive_rate)}, attack recall ${formatPercent(threshold.chosen.attack_recall)}`
                  : '—',
              },
            ]}
          />
          {threshold?.chosen && metrics.test && (
            <p className="text-xs text-slate-500">
              The testing-file row uses the default decision (highest class). The testing file’s
              distribution differs from the training file, so its false-positive rate at the
              threshold is expected to be higher than on validation; it has not been measured.
            </p>
          )}
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
            Precision per class ({precisionSource})
          </h3>
          <DataTable
            caption={`Precision per class on the ${precisionSource} data`}
            rows={Object.entries(precision)}
            rowKey={([name]) => name}
            empty={<p className="text-sm text-slate-500">Not recorded.</p>}
            columns={[
              { key: 'class', header: 'Class', render: ([name]) => name },
              {
                key: 'p',
                header: 'Precision',
                className: 'tabular-nums',
                render: ([, p]) => formatPercent(p),
              },
              {
                key: 'note',
                header: '',
                render: ([name]) =>
                  unreliable.has(name) ? (
                    <StatusBadge tone="warning" label="Unreliable label" />
                  ) : null,
              },
            ]}
          />
          <p className="mt-2 text-xs text-slate-500">
            Precision is the share of records predicted as a class that really were that class.
            Below 50%, most alerts with that suspected category belong to another class, so
            recommendations never suggest containment for it.
          </p>
        </div>
      </div>
      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-medium text-cyan-700">
          Features ({model.features.length}) and artifact
        </summary>
        <div className="mt-2 space-y-2 text-xs text-slate-600">
          <p>
            SHA-256 <span className="break-all font-mono">{model.artifact_sha256}</span> (the
            backend loads the file only if it still matches)
          </p>
          <p className="font-mono">{model.features.join(', ')}</p>
          <p>Classes: {model.class_labels.join(', ')}</p>
        </div>
      </details>

      {confirming && (
        <ConfirmDialog
          title={`Activate ${model.name} ${model.version}?`}
          confirmLabel="Activate model"
          pending={action.pending}
          error={action.error}
          onConfirm={async () => {
            if (await action.run()) {
              setConfirming(false)
              onActivated()
            }
          }}
          onCancel={() => setConfirming(false)}
        >
          <p>
            It replaces the active <strong>{model.feature_profile}</strong> model for new analyses.
            Existing alerts keep the model that produced them. The change is audited.
          </p>
        </ConfirmDialog>
      )}
    </Panel>
  )
}
