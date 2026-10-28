import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function IncidentsPage() {
  return (
    <>
      <PageHeader
        title="Incidents"
        description="Analyst-managed investigations. Incidents are confirmed by people, never by the model."
      />
      <PlannedFeature
        phase={4}
        items={[
          'Create investigations from one or more alerts',
          'Notes, assignment, and status: new, under investigation, confirmed, false positive, resolved',
          'History of previous actions',
        ]}
      />
    </>
  )
}
