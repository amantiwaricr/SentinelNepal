import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { fillDays } from '../../lib/activity'
import type { ActivityPoint } from '../../types/api'

interface ActivityChartProps {
  points: ActivityPoint[]
  generatedAt: string
  days: number
}

export function ActivityChart({ points, generatedAt, days }: ActivityChartProps) {
  const data = fillDays(points, generatedAt, days)
  return (
    <figure>
      <div aria-hidden="true" className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip cursor={{ fill: '#f1f5f9' }} />
            <Bar dataKey="count" name="Alerts" fill="#0e7490" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">
        Alerts created per day (UTC): {data.map((d) => `${d.label}: ${d.count}`).join('; ')}
      </figcaption>
    </figure>
  )
}
