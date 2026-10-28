import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function AlertsPage() {
  return (
    <>
      <PageHeader
        title="Alerts"
        description="Model-generated alerts awaiting analyst review. A predicted category is not proof of an attack."
      />
      <PlannedFeature
        phase={4}
        items={[
          'Search by source or destination IP',
          'Filters for time range, predicted category, severity, status, and source (live or dataset)',
          'Pagination and sorting',
          'Links to alert details, IP history, and investigations',
        ]}
      />
    </>
  )
}
