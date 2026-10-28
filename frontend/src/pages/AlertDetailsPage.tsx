import { Link, useParams } from 'react-router'

import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function AlertDetailsPage() {
  const { alertId } = useParams()
  return (
    <>
      <PageHeader
        title={`Alert ${alertId ?? ''}`}
        description="Evidence behind a single prediction."
        actions={
          <Link to="/alerts" className="text-sm font-medium text-cyan-700 hover:text-cyan-900">
            Back to alerts
          </Link>
        }
      />
      <PlannedFeature
        phase={4}
        items={[
          'Flow metadata, predicted category, and uncalibrated model score',
          'Input features, unavailable features, and global feature importance',
          'Recommendations, related IP history, and linked investigations',
        ]}
      />
    </>
  )
}
