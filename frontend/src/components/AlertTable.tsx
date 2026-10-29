import { Link } from 'react-router'

import { formatDateTime, formatEndpoint } from '../lib/format'
import { ALERT_STATUS_LABELS, ALERT_STATUS_TONE } from '../lib/labels'
import type { AlertOut } from '../types/api'
import { AttackScore } from './AttackScore'
import { DataTable } from './DataTable'
import { EmptyState } from './EmptyState'
import { SeverityBadge } from './SeverityBadge'
import { SourceTag } from './SourceTag'
import { StatusBadge } from './StatusBadge'

function IpLink({ ip, port }: { ip: string | null; port: number | null }) {
  if (!ip) return <span className="text-slate-400">—</span>
  return (
    <Link
      to={`/ips?ip=${encodeURIComponent(ip)}`}
      className="font-mono text-xs text-cyan-700 hover:underline"
      title={`Investigate ${ip}`}
    >
      {formatEndpoint(ip, port)}
    </Link>
  )
}

interface AlertTableProps {
  alerts: AlertOut[]
  caption: string
  empty?: React.ReactNode
}

export function AlertTable({ alerts, caption, empty }: AlertTableProps) {
  return (
    <DataTable
      caption={caption}
      rows={alerts}
      rowKey={(alert) => alert.id}
      empty={empty ?? <EmptyState title="No alerts match" />}
      columns={[
        {
          key: 'id',
          header: 'Alert',
          render: (a) => (
            <Link to={`/alerts/${a.id}`} className="font-medium text-cyan-700 hover:underline">
              #{a.id}
            </Link>
          ),
        },
        {
          key: 'created',
          header: 'Created',
          className: 'whitespace-nowrap',
          render: (a) => (
            <div className="space-y-1">
              <div>{formatDateTime(a.created_at)}</div>
              <SourceTag source={a.source} />
            </div>
          ),
        },
        { key: 'src', header: 'Source', render: (a) => <IpLink ip={a.src_ip} port={a.src_port} /> },
        {
          key: 'dst',
          header: 'Destination',
          render: (a) => <IpLink ip={a.dst_ip} port={a.dst_port} />,
        },
        {
          key: 'proto',
          header: 'Protocol',
          render: (a) => (
            <span className="text-xs text-slate-600">
              {[a.protocol, a.service && a.service !== '-' ? a.service : null]
                .filter(Boolean)
                .join(' / ') || '—'}
            </span>
          ),
        },
        {
          key: 'category',
          header: 'Suspected category',
          render: (a) => a.predicted_category,
        },
        {
          key: 'score',
          header: 'Attack score',
          render: (a) => <AttackScore score={a.attack_score} />,
        },
        {
          key: 'severity',
          header: 'Severity',
          render: (a) => <SeverityBadge severity={a.severity} />,
        },
        {
          key: 'status',
          header: 'Status',
          render: (a) => (
            <StatusBadge tone={ALERT_STATUS_TONE[a.status]} label={ALERT_STATUS_LABELS[a.status]} />
          ),
        },
      ]}
    />
  )
}
