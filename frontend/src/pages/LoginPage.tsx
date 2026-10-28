import { ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'

export function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-900 p-4">
      <section className="w-full max-w-sm rounded-lg bg-white p-6 shadow-lg">
        <div className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <ShieldCheck aria-hidden="true" className="h-6 w-6 text-cyan-600" />
          <h1>Sign in to SentinelNepal</h1>
        </div>
        <p className="mt-3 text-sm text-slate-600">
          Authentication (administrator and analyst accounts) is implemented in Phase 3. Until then
          there is no sign-in form, so no credentials are collected.
        </p>
        <Link
          to="/"
          className="mt-4 inline-block text-sm font-medium text-cyan-700 hover:text-cyan-900"
        >
          Continue to the dashboard
        </Link>
      </section>
    </main>
  )
}
