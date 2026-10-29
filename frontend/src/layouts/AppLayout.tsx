import { LogOut, Menu, ShieldCheck, UserRound, X } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'

import { useAuth, useCurrentUser } from '../auth/AuthContext'
import { UserDirectoryProvider } from '../auth/UserDirectory'
import { LiveEventsProvider } from '../events/LiveEventsProvider'
import { navItemsFor } from './navigation'

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const closeSidebar = () => setSidebarOpen(false)
  const user = useCurrentUser()
  const { logout } = useAuth()
  const navigate = useNavigate()

  async function signOut() {
    await logout()
    navigate('/login', { replace: true, state: { reason: 'signed_out' } })
  }

  return (
    <UserDirectoryProvider>
      <LiveEventsProvider>
        <div className="min-h-screen bg-slate-100 lg:flex">
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
          >
            Skip to content
          </a>

          {sidebarOpen && (
            <div
              aria-hidden="true"
              className="fixed inset-0 z-30 bg-slate-900/50 lg:hidden"
              onClick={closeSidebar}
            />
          )}

          <aside
            id="sidebar"
            className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-slate-900 text-slate-200 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
              sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
          >
            <div className="flex h-16 items-center justify-between border-b border-slate-800 px-5">
              <Link
                to="/"
                className="flex items-center gap-2 font-semibold text-white"
                onClick={closeSidebar}
              >
                <ShieldCheck aria-hidden="true" className="h-6 w-6 text-cyan-400" />
                SentinelNepal
              </Link>
              <button
                type="button"
                className="rounded p-1 text-slate-400 hover:text-white lg:hidden"
                onClick={closeSidebar}
                aria-label="Close navigation"
              >
                <X aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>
            <nav aria-label="Primary" className="flex-1 overflow-y-auto px-3 py-4">
              <ul className="space-y-1">
                {navItemsFor(user.role).map(({ to, label, icon: Icon }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={to === '/'}
                      onClick={closeSidebar}
                      className={({ isActive }) =>
                        `flex items-center gap-3 rounded-md border-l-2 px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                          isActive
                            ? 'border-cyan-400 bg-slate-800 text-white'
                            : 'border-transparent text-slate-300 hover:bg-slate-800/60 hover:text-white'
                        }`
                      }
                    >
                      <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                      {label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
            <p className="border-t border-slate-800 px-5 py-3 text-xs text-slate-400">
              Model output is a prediction, not proof of an attack.
            </p>
          </aside>

          <div className="flex min-w-0 flex-1 flex-col">
            <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
              <button
                type="button"
                className="rounded p-1 text-slate-600 hover:text-slate-900 lg:hidden"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open navigation"
                aria-controls="sidebar"
                aria-expanded={sidebarOpen}
              >
                <Menu aria-hidden="true" className="h-5 w-5" />
              </button>
              <span className="hidden text-sm text-slate-500 sm:inline">
                Security operations dashboard · isolated lab
              </span>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-sm text-slate-700">
                  <UserRound aria-hidden="true" className="h-4 w-4 text-slate-400" />
                  <span className="font-medium">{user.username}</span>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs capitalize text-slate-600">
                    {user.role}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={signOut}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600"
                >
                  <LogOut aria-hidden="true" className="h-4 w-4" />
                  Sign out
                </button>
              </div>
            </header>
            <main id="main-content" className="flex-1 p-4 sm:p-6 lg:p-8">
              <Outlet />
            </main>
          </div>
        </div>
      </LiveEventsProvider>
    </UserDirectoryProvider>
  )
}
