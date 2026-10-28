import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function ModelEvaluationPage() {
  return (
    <>
      <PageHeader
        title="Model Evaluation"
        description="Metrics from real evaluation runs on the UNSW-NB15 dataset."
      />
      <PlannedFeature
        phase={2}
        items={[
          'Precision, recall, F1-score, and false-positive rate per class',
          'Confusion matrix and inference latency',
          'Model version, feature profile, and live-compatibility status',
        ]}
      />
    </>
  )
}
