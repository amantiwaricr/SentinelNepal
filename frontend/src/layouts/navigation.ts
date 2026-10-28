import {
  Activity,
  BrainCircuit,
  FolderSearch,
  LayoutDashboard,
  Lightbulb,
  Network,
  ScrollText,
  ShieldAlert,
  ShieldBan,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/alerts', label: 'Alerts', icon: ShieldAlert },
  { to: '/ips', label: 'IP Investigation', icon: Network },
  { to: '/incidents', label: 'Incidents', icon: FolderSearch },
  { to: '/recommendations', label: 'Recommendations', icon: Lightbulb },
  { to: '/firewall', label: 'Firewall Approvals', icon: ShieldBan },
  { to: '/audit', label: 'Audit Logs', icon: ScrollText },
  { to: '/model', label: 'Model Evaluation', icon: BrainCircuit },
  { to: '/system', label: 'System Health', icon: Activity },
]
