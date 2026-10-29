import { ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router'

import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/Button'
import { FormError } from '../components/FormError'
import { Field } from '../components/FormField'
import { Notice } from '../components/Notice'
import { useAction } from '../hooks/useAction'
import { safeNextPath } from '../lib/navigation'

export function LoginPage() {
  const { state, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const next = safeNextPath(params.get('next'))
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { run, pending, error } = useAction(login)

  const reason =
    state.status === 'anonymous'
      ? (state.reason ?? (location.state as { reason?: string } | null)?.reason)
      : undefined

  if (state.status === 'authenticated') return <Navigate to={next} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    const user = await run({ username: username.trim(), password })
    // Drop the password from memory as soon as the attempt finishes.
    setPassword('')
    if (user) navigate(next, { replace: true })
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-900 p-4">
      <section className="w-full max-w-sm rounded-lg bg-white p-6 shadow-lg">
        <div className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <ShieldCheck aria-hidden="true" className="h-6 w-6 text-cyan-600" />
          <h1>Sign in to SentinelNepal</h1>
        </div>
        <p className="mt-1 text-sm text-slate-500">Security operations dashboard · isolated lab</p>

        <div className="mt-4 space-y-3">
          {reason === 'expired' && (
            <Notice tone="warning">Your session has ended. Please sign in again.</Notice>
          )}
          {reason === 'signed_out' && <Notice>You have signed out.</Notice>}
        </div>

        {state.status === 'checking' ? (
          <p role="status" className="mt-4 text-sm text-slate-600">
            Checking your session…
          </p>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-4" noValidate>
            <Field label="Username">
              {(props) => (
                <input
                  {...props}
                  name="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  required
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              )}
            </Field>
            <Field label="Password">
              {(props) => (
                <input
                  {...props}
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              )}
            </Field>
            <FormError error={error} />
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={pending || !username.trim() || !password}
            >
              {pending ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        )}
        <p className="mt-5 text-xs text-slate-500">
          Accounts are created by an administrator. After repeated failed attempts an account is
          locked for a short time.
        </p>
      </section>
    </main>
  )
}
