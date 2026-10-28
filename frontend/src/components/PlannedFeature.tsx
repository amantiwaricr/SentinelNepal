import { Construction } from 'lucide-react'

interface PlannedFeatureProps {
  phase: number
  items: string[]
}

/** Honest placeholder for pages whose data and workflows arrive in a later phase. */
export function PlannedFeature({ phase, items }: PlannedFeatureProps) {
  return (
    <section
      aria-label="Planned functionality"
      className="rounded-lg border border-dashed border-slate-300 bg-white p-6"
    >
      <div className="flex items-center gap-2 text-slate-700">
        <Construction aria-hidden="true" className="h-5 w-5 text-amber-600" />
        <h2 className="font-medium">Not implemented yet — planned for Phase {phase}</h2>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        No data is shown here until the backing API exists. This page will provide:
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}
