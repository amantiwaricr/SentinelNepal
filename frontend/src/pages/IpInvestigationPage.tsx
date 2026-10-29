import { Search } from 'lucide-react'
import { useCallback, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { AlertTable } from '../components/AlertTable'
import { Button } from '../components/Button'
import { CountList } from '../components/CountList'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { Field } from '../components/FormField'
import { KeyValueList } from '../components/KeyValueList'
import { LoadingState } from '../components/LoadingState'
import { Notice } from '../components/Notice'
import { PageHeader } from '../components/PageHeader'
import { Panel } from '../components/Panel'
import { SeverityBadge } from '../components/SeverityBadge'
import { useApiResource } from '../hooks/useApiResource'
import { formatCount, formatDateTime } from '../lib/format'
import { SEVERITIES } from '../lib/labels'
import { text } from '../lib/params'
import { getIpSummary, getSubnetSummary } from '../services/api/investigation'
import type { IpSummaryOut, Severity, SubnetSummaryOut } from '../types/api'

const NO_ENRICHMENT =
  'Only alerts stored by SentinelNepal are shown. No geolocation, ownership or threat-intelligence lookups are performed, so nothing here identifies who is behind an address.'

export function IpInvestigationPage() {
  const [params, setParams] = useSearchParams()
  const ip = text(params.get('ip'))
  const cidr = text(params.get('cidr'))

  return (
    <>
      <PageHeader
        title="IP Investigation"
        description="What SentinelNepal has recorded about an address or network."
      />
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SearchForm
          key={`ip-${ip ?? ''}`}
          label="IP address"
          placeholder="e.g. 175.45.176.1"
          initial={ip ?? ''}
          submitLabel="Investigate address"
          onSearch={(value) => setParams({ ip: value })}
        />
        <SearchForm
          key={`cidr-${cidr ?? ''}`}
          label="Subnet (CIDR)"
          placeholder="e.g. 175.45.176.0/24"
          hint="IPv4 /16 or narrower, IPv6 /48 or narrower"
          initial={cidr ?? ''}
          submitLabel="Investigate subnet"
          onSearch={(value) => setParams({ cidr: value })}
        />
      </div>

      {ip && <IpSummary ip={ip} key={ip} />}
      {!ip && cidr && <SubnetSummary cidr={cidr} key={cidr} />}
      {!ip && !cidr && (
        <Panel>
          <EmptyState title="Enter an address or subnet">
            You can also open an investigation from any IP address shown on an alert.
          </EmptyState>
        </Panel>
      )}
    </>
  )
}

function SearchForm({
  label,
  placeholder,
  hint,
  initial,
  submitLabel,
  onSearch,
}: {
  label: string
  placeholder: string
  hint?: string
  initial: string
  submitLabel: string
  onSearch: (value: string) => void
}) {
  const [value, setValue] = useState(initial)
  function submit(event: FormEvent) {
    event.preventDefault()
    if (value.trim()) onSearch(value.trim())
  }
  return (
    <Panel>
      <form onSubmit={submit} className="flex items-end gap-2">
        <Field label={label} hint={hint} className="flex-1">
          {(props) => (
            <input
              {...props}
              value={value}
              placeholder={placeholder}
              spellCheck={false}
              onChange={(e) => setValue(e.target.value)}
            />
          )}
        </Field>
        <Button
          type="submit"
          variant="primary"
          aria-label={submitLabel}
          className={hint ? 'mb-5' : ''}
        >
          <Search aria-hidden="true" className="h-4 w-4" />
          <span className="hidden sm:inline">Search</span>
        </Button>
      </form>
    </Panel>
  )
}

function IpSummary({ ip }: { ip: string }) {
  const load = useCallback((signal: AbortSignal) => getIpSummary(ip, signal), [ip])
  const { state, reload } = useApiResource(load)
  if (state.status === 'loading') return <LoadingState label={`Looking up ${ip}…`} />
  if (state.status === 'error') {
    return <ErrorState title={`Could not investigate ${ip}`} error={state.error} onRetry={reload} />
  }
  return <IpSummaryView data={state.data} />
}

function IpSummaryView({ data }: { data: IpSummaryOut }) {
  return (
    <div className="space-y-6">
      <Notice>{data.note || NO_ENRICHMENT}</Notice>
      <Panel
        title={`Address ${data.ip}`}
        description={`IPv${data.version}`}
        actions={
          <Link
            to={`/alerts?src_ip=${encodeURIComponent(data.ip)}`}
            className="text-sm text-cyan-700 hover:underline"
          >
            Alerts with this source
          </Link>
        }
      >
        <KeyValueList
          columns={3}
          items={[
            { label: 'Alerts involving this address', value: formatCount(data.alerts_total) },
            { label: 'As source', value: formatCount(data.alerts_as_source) },
            { label: 'As destination', value: formatCount(data.alerts_as_destination) },
            { label: 'First seen', value: formatDateTime(data.first_seen) },
            { label: 'Last seen', value: formatDateTime(data.last_seen) },
            {
              label: 'Observed subnet',
              value: (
                <Link
                  to={`/ips?cidr=${encodeURIComponent(data.containing_subnet)}`}
                  className="font-mono text-cyan-700 hover:underline"
                >
                  {data.containing_subnet}
                </Link>
              ),
            },
            { label: 'Alerts in that subnet', value: formatCount(data.alerts_in_subnet) },
          ]}
        />
      </Panel>

      {data.alerts_total === 0 ? (
        <Panel>
          <EmptyState title="No alerts involve this address">
            The address has not appeared as a source or destination in any stored alert.
          </EmptyState>
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
            <Panel title="Suspected categories">
              <CountList counts={data.by_category} />
            </Panel>
            <Panel title="Severity">
              <CountList
                counts={data.by_severity}
                order={SEVERITIES}
                renderLabel={(k) => <SeverityBadge severity={k as Severity} />}
              />
            </Panel>
            <Panel title="Destination ports">
              <CountList counts={data.destination_ports} />
            </Panel>
            <Panel title="Protocols">
              <CountList counts={data.protocols} />
            </Panel>
          </div>
          <Panel title="Recent alerts" flush>
            <AlertTable
              alerts={data.recent_alerts}
              caption={`Recent alerts involving ${data.ip}`}
            />
          </Panel>
        </>
      )}
    </div>
  )
}

function SubnetSummary({ cidr }: { cidr: string }) {
  const load = useCallback((signal: AbortSignal) => getSubnetSummary(cidr, signal), [cidr])
  const { state, reload } = useApiResource(load)
  if (state.status === 'loading') return <LoadingState label={`Looking up ${cidr}…`} />
  if (state.status === 'error') {
    return (
      <ErrorState title={`Could not investigate ${cidr}`} error={state.error} onRetry={reload} />
    )
  }
  return <SubnetSummaryView data={state.data} />
}

function IpCounts({ counts }: { counts: Record<string, number> }) {
  return (
    <CountList
      counts={counts}
      renderLabel={(ip) => (
        <Link
          to={`/ips?ip=${encodeURIComponent(ip)}`}
          className="font-mono text-cyan-700 hover:underline"
        >
          {ip}
        </Link>
      )}
    />
  )
}

function SubnetSummaryView({ data }: { data: SubnetSummaryOut }) {
  return (
    <div className="space-y-6">
      <Notice>{NO_ENRICHMENT}</Notice>
      <Panel
        title={`Subnet ${data.cidr}`}
        actions={
          <Link
            to={`/alerts?cidr=${encodeURIComponent(data.cidr)}`}
            className="text-sm text-cyan-700 hover:underline"
          >
            Alerts in this subnet
          </Link>
        }
      >
        <KeyValueList
          columns={3}
          items={[
            {
              label: 'Alerts (source or destination inside)',
              value: formatCount(data.alerts_total),
            },
            { label: 'First seen', value: formatDateTime(data.first_seen) },
            { label: 'Last seen', value: formatDateTime(data.last_seen) },
          ]}
        />
      </Panel>
      {data.alerts_total === 0 ? (
        <Panel>
          <EmptyState title="No alerts involve this subnet" />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Panel title="Suspected categories">
            <CountList counts={data.by_category} />
          </Panel>
          <Panel title="Top source addresses">
            <IpCounts counts={data.top_source_ips} />
          </Panel>
          <Panel title="Top destination addresses">
            <IpCounts counts={data.top_destination_ips} />
          </Panel>
        </div>
      )}
    </div>
  )
}
