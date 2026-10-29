import { Lightbulb } from 'lucide-react'
import { Link } from 'react-router'

import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'

/**
 * The rule engine that creates recommendations is Phase 5. Stored recommendations are shown
 * on each alert's page; this page explains what will appear here rather than inventing any.
 */
export function RecommendationsPage() {
  return (
    <>
      <PageHeader
        title="Recommendations"
        description="Suggested defensive actions for suspected attack categories."
      />
      <div className="max-w-3xl space-y-4">
        <Notice title="The recommendation engine is added in Phase 5">
          No recommendations are generated yet, so none are shown. Nothing on this page is
          placeholder data.
        </Notice>
        <Panel>
          <div className="flex gap-3">
            <Lightbulb aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
            <div className="space-y-2 text-sm text-slate-700">
              <p>From Phase 5, each recommendation will state:</p>
              <ul className="list-disc space-y-1 pl-5">
                <li>the suggested action and the rule (and rule version) that produced it;</li>
                <li>the evidence the rule needs, and which of it the alert actually has;</li>
                <li>its limitations, since predicted categories can be wrong;</li>
                <li>whether it needs human approval (any firewall block always does).</li>
              </ul>
              <p>
                Recommendations will appear on each{' '}
                <Link to="/alerts" className="text-cyan-700 hover:underline">
                  alert's page
                </Link>
                . Unknown or unreliable categories will get “investigate further” rather than a
                specific action.
              </p>
            </div>
          </div>
        </Panel>
      </div>
    </>
  )
}
