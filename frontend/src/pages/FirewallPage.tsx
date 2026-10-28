import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function FirewallPage() {
  return (
    <>
      <PageHeader
        title="Firewall Approvals"
        description="Administrator-approved, temporary nftables blocks in the isolated lab."
      />
      <PlannedFeature
        phase={7}
        items={[
          'Target IP or CIDR, reason, requester, and approver',
          'Approval status with an explicit confirmation step',
          'Expiry time, execution result confirmed by the firewall helper, and reversal status',
        ]}
      />
    </>
  )
}
