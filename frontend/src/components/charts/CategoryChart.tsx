import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface CategoryChartProps {
  counts: Record<string, number>
}

/** Alerts per predicted category (horizontal bars, largest first). */
export function CategoryChart({ counts }: CategoryChartProps) {
  const data = Object.entries(counts)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)
  return (
    <figure>
      <div aria-hidden="true" style={{ height: Math.max(120, data.length * 30 + 30) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="category" width={110} tick={{ fontSize: 11 }} />
            <Tooltip cursor={{ fill: '#f1f5f9' }} />
            <Bar dataKey="count" name="Alerts" fill="#475569" radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">
        Alerts by predicted category: {data.map((d) => `${d.category}: ${d.count}`).join('; ')}
      </figcaption>
    </figure>
  )
}
