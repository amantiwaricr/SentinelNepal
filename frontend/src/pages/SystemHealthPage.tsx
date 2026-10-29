import { RefreshCw, UserPlus } from 'lucide-react'
import { useCallback, useState } from 'react'

import { useCurrentUser } from '../auth/AuthContext'
import { useUserDirectory } from '../auth/userDirectoryContext'
import { Button } from '../components/Button'
import { ComponentHealthList } from '../components/ComponentHealthList'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DataTable } from '../components/DataTable'
import { ErrorState } from '../components/ErrorState'
import { Field } from '../components/FormField'
import { LoadingState } from '../components/LoadingState'
import { PageHeader } from '../components/PageHeader'
import { Pagination } from '../components/Pagination'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { useAction } from '../hooks/useAction'
import { useApiResource } from '../hooks/useApiResource'
import { formatDateTime } from '../lib/format'
import { getComponents, getReadiness } from '../services/api/health'
import { createUser, listUsers, updateUser } from '../services/api/users'
import type { Role, UserOut, UserUpdate } from '../types/api'

export function SystemHealthPage() {
  const user = useCurrentUser()
  const readiness = useApiResource(getReadiness)
  const components = useApiResource(getComponents)

  return (
    <>
      <PageHeader
        title="System & Settings"
        description="Component status reported by the backend, and account management."
        actions={
          <Button
            onClick={() => {
              readiness.reload()
              components.reload()
            }}
          >
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
            Refresh
          </Button>
        }
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Backend API">
          {readiness.state.status === 'loading' && (
            <LoadingState label="Checking backend status…" />
          )}
          {readiness.state.status === 'error' && (
            <ErrorState
              title="Backend status unavailable"
              error={readiness.state.error}
              onRetry={readiness.reload}
            />
          )}
          {readiness.state.status === 'success' && (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <StatusBadge
                  tone={readiness.state.data.status === 'ready' ? 'success' : 'danger'}
                  label={readiness.state.data.status === 'ready' ? 'Ready' : 'Not ready'}
                />
                <span className="text-sm text-slate-500">
                  v{readiness.state.data.version} · {readiness.state.data.environment}
                </span>
              </div>
              <ComponentHealthList components={readiness.state.data.components} />
            </>
          )}
        </Panel>
        <Panel title="Detection components">
          {components.state.status === 'loading' && <LoadingState />}
          {components.state.status === 'error' && (
            <ErrorState
              title="Component status unavailable"
              error={components.state.error}
              onRetry={components.reload}
            />
          )}
          {components.state.status === 'success' && (
            <ComponentHealthList
              components={Object.fromEntries(
                Object.entries(components.state.data.components).filter(
                  ([name]) => name !== 'database' && name !== 'migrations',
                ),
              )}
            />
          )}
        </Panel>
      </div>
      {user.role === 'admin' && <UsersPanel />}
    </>
  )
}

const PAGE_SIZE = 50

function UsersPanel() {
  const me = useCurrentUser()
  const directory = useUserDirectory()
  const [page, setPage] = useState(1)
  const load = useCallback(
    (signal: AbortSignal) => listUsers({ page, page_size: PAGE_SIZE }, signal),
    [page],
  )
  const { state, reload } = useApiResource(load)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<UserOut | null>(null)

  const changed = () => {
    reload({ quiet: true })
    directory.reload()
  }

  return (
    <Panel
      title="Users"
      description="Administrators manage accounts. Passwords are hashed with Argon2id and never shown."
      className="mt-6"
      flush
      actions={
        <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
          <UserPlus aria-hidden="true" className="h-4 w-4" />
          Add user
        </Button>
      }
    >
      {state.status === 'loading' && <LoadingState label="Loading users…" />}
      {state.status === 'error' && (
        <div className="p-4">
          <ErrorState title="Users unavailable" error={state.error} onRetry={reload} />
        </div>
      )}
      {state.status === 'success' && (
        <>
          <DataTable
            caption="User accounts"
            rows={state.data.items}
            rowKey={(u) => u.id}
            columns={[
              {
                key: 'name',
                header: 'Username',
                render: (u) => (
                  <span className="font-medium">
                    {u.username}
                    {u.id === me.id && <span className="ml-1 text-xs text-slate-500">(you)</span>}
                  </span>
                ),
              },
              { key: 'role', header: 'Role', className: 'capitalize', render: (u) => u.role },
              {
                key: 'active',
                header: 'Account',
                render: (u) => (
                  <StatusBadge
                    tone={u.is_active ? 'success' : 'neutral'}
                    label={u.is_active ? 'Active' : 'Disabled'}
                  />
                ),
              },
              {
                key: 'login',
                header: 'Last sign-in',
                render: (u) => formatDateTime(u.last_login_at),
              },
              { key: 'created', header: 'Created', render: (u) => formatDateTime(u.created_at) },
              {
                key: 'actions',
                header: <span className="sr-only">Actions</span>,
                render: (u) => (
                  <Button
                    size="sm"
                    onClick={() => setEditing(u)}
                    aria-label={`Manage ${u.username}`}
                  >
                    Manage
                  </Button>
                ),
              },
            ]}
          />
          <Pagination
            page={state.data.page}
            pageSize={state.data.page_size}
            total={state.data.total}
            onPageChange={setPage}
          />
        </>
      )}
      {creating && (
        <CreateUserDialog
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false)
            changed()
          }}
        />
      )}
      {editing && (
        <EditUserDialog
          user={editing}
          isSelf={editing.id === me.id}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            changed()
          }}
        />
      )}
    </Panel>
  )
}

const PASSWORD_HINT =
  'At least 12 characters, must not contain the username. Give it to the user over a secure channel.'

function CreateUserDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('analyst')
  const action = useAction(createUser)

  return (
    <ConfirmDialog
      title="Add user"
      confirmLabel="Create user"
      pending={action.pending}
      confirmDisabled={!username.trim() || !password}
      error={action.error}
      onConfirm={async () => {
        if (await action.run({ username: username.trim(), password, role })) onCreated()
      }}
      onCancel={onClose}
    >
      <Field label="Username" hint="3–64 letters, digits, dots, dashes or underscores">
        {(props) => (
          <input
            {...props}
            autoComplete="off"
            spellCheck={false}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        )}
      </Field>
      <Field label="Initial password" hint={PASSWORD_HINT}>
        {(props) => (
          <input
            {...props}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
      </Field>
      <Field label="Role">
        {(props) => (
          <select {...props} value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="analyst">Analyst</option>
            <option value="admin">Admin</option>
          </select>
        )}
      </Field>
    </ConfirmDialog>
  )
}

function EditUserDialog({
  user,
  isSelf,
  onClose,
  onSaved,
}: {
  user: UserOut
  isSelf: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const [role, setRole] = useState<Role>(user.role)
  const [active, setActive] = useState(user.is_active)
  const [password, setPassword] = useState('')
  const action = useAction((body: UserUpdate) => updateUser(user.id, body))

  async function confirm() {
    const body: UserUpdate = {}
    if (role !== user.role) body.role = role
    if (active !== user.is_active) body.is_active = active
    if (password) body.password = password
    if (Object.keys(body).length === 0 || (await action.run(body))) onSaved()
  }

  return (
    <ConfirmDialog
      title={`Manage ${user.username}`}
      confirmLabel="Save changes"
      pending={action.pending}
      error={action.error}
      onConfirm={confirm}
      onCancel={onClose}
    >
      {isSelf && (
        <p className="text-xs text-slate-500">
          You cannot remove your own admin role or disable your own account.
        </p>
      )}
      <Field label="Role">
        {(props) => (
          <select
            {...props}
            value={role}
            disabled={isSelf}
            onChange={(e) => setRole(e.target.value as Role)}
          >
            <option value="analyst">Analyst</option>
            <option value="admin">Admin</option>
          </select>
        )}
      </Field>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={active}
          disabled={isSelf}
          onChange={(e) => setActive(e.target.checked)}
          className="rounded border-slate-300 text-cyan-700 focus:ring-cyan-600"
        />
        Account active (disabling signs the user out everywhere)
      </label>
      <Field
        label="Reset password (optional)"
        hint={`${PASSWORD_HINT} Resetting signs the user out everywhere.`}
      >
        {(props) => (
          <input
            {...props}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
      </Field>
    </ConfirmDialog>
  )
}
