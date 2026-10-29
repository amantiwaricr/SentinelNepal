/** Display helpers. Timestamps from the API are UTC ISO strings. */

const dateTime = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' })
const integer = new Intl.NumberFormat()

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateTime.format(date)
}

/** A calendar day as returned by the dashboard's per-day buckets (UTC). */
export function formatDay(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateOnly.format(date)
}

export function formatCount(value: number): string {
  return integer.format(value)
}

/** Fractions such as 0.9025 as "90.3%". */
export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

/** Attack scores are uncalibrated, so they are shown as plain numbers, not percentages. */
export function formatScore(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(3)
}

export function formatDuration(seconds: number): string {
  if (seconds % 3600 === 0) return `${seconds / 3600} h`
  if (seconds % 60 === 0) return `${seconds / 60} min`
  return `${seconds} s`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function humanize(value: string): string {
  const text = value.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** "src_ip:port" style endpoint, omitting what is unknown. */
export function formatEndpoint(ip: string | null, port: number | null): string {
  if (!ip) return '—'
  if (port == null) return ip
  return ip.includes(':') ? `[${ip}]:${port}` : `${ip}:${port}`
}

/** A datetime-local input value (local time) as an ISO string for the API, or undefined. */
export function localInputToIso(value: string): string | undefined {
  if (!value) return undefined
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
}

export function isoToLocalInput(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
