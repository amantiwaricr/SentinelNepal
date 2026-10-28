import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function DashboardPage() {
  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Overview of alerts, incidents, and component health."
      />
      <PlannedFeature
        phase={4}
        items={[
          'Total and new alert counts, by severity and by predicted category',
          'Recent alert activity and frequently observed source IPs',
          'Incident status summary',
          'Collector and model health, with live data labelled separately from dataset analysis',
        ]}
      />
    </>
  )
}
