import {
  Activity,
  BrainCircuit,
  FileSpreadsheet,
  FolderSearch,
  LayoutDashboard,
  Lightbulb,
  Network,
  ScrollText,
  ShieldAlert,
  ShieldBan,
  type LucideIcon,
} from 'lucide-react'

import type { Role } from '../types/api'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Hidden from other roles. The API enforces the same rule; this only tidies the menu. */
  role?: Role
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/alerts', label: 'Alerts', icon: ShieldAlert },
  { to: '/ips', label: 'IP Investigation', icon: Network },
  { to: '/incidents', label: 'Incidents', icon: FolderSearch },
  { to: '/recommendations', label: 'Recommendations', icon: Lightbulb },
  { to: '/firewall', label: 'Firewall Approvals', icon: ShieldBan },
  { to: '/datasets', label: 'Dataset Analysis', icon: FileSpreadsheet },
  { to: '/model', label: 'Model Evaluation', icon: BrainCircuit },
  { to: '/audit', label: 'Audit Logs', icon: ScrollText, role: 'admin' },
  { to: '/system', label: 'System & Settings', icon: Activity },
]

export function navItemsFor(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.role || item.role === role)
}
