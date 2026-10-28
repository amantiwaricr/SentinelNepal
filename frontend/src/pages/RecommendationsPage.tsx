import { PageHeader } from '../components/PageHeader'
import { PlannedFeature } from '../components/PlannedFeature'

export function RecommendationsPage() {
  return (
    <>
      <PageHeader
        title="Recommendations"
        description="Rule-based defensive guidance tied to alert evidence."
      />
      <PlannedFeature
        phase={5}
        items={[
          'Recommended action, reason, and priority for each alert category',
          'Evidence required and evidence actually present',
          'Limitations and whether human approval is required',
        ]}
      />
    </>
  )
}
