import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function IpInvestigationPage() {
  return (
    <>
      <PageHeader
        title="IP Investigation"
        description="History of alerts involving an address or subnet, using only observed data."
      />
      <PlannedFeature
        phase={4}
        items={[
          'Source/destination addresses, ports, and protocols where the data provides them',
          'First and last observation times and related alerts',
          'Containing subnet (/24 or /64) aggregation',
          'Evidence and model version for each related alert',
        ]}
      />
    </>
  )
}
