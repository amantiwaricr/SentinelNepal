import type { ActivityPoint } from '../types/api'
import { formatDay } from './format'

const DAY_MS = 24 * 60 * 60 * 1000

/** Fills days without alerts with zero so gaps in activity are visible, not hidden. */
export function fillDays(points: ActivityPoint[], endIso: string, days: number) {
  const counts = new Map(points.map((p) => [p.day.slice(0, 10), p.count]))
  const end = new Date(endIso)
  const endDay = Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate())
  return Array.from({ length: days }, (_, i) => {
    const day = new Date(endDay - (days - 1 - i) * DAY_MS).toISOString().slice(0, 10)
    return { day, label: formatDay(day), count: counts.get(day) ?? 0 }
  })
}
