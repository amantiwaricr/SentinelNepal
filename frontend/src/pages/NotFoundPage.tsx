import { Link } from 'react-router'

import { PageHeader } from '../components/PageHeader'

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" description="The page you requested does not exist." />
      <Link to="/" className="text-sm font-medium text-cyan-700 hover:text-cyan-900">
        Go to the dashboard
      </Link>
    </>
  )
}
