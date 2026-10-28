import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function AuditLogsPage() {
  return (
    <>
      <PageHeader
        title="Audit Logs"
        description="Append-only record of security-relevant actions (administrators only)."
      />
      <PlannedFeature
        phase={3}
        items={[
          'Actor, action, target, outcome, and timestamp for each entry',
          'Filters by actor, action, target, and time range',
        ]}
      />
    </>
  )
}
