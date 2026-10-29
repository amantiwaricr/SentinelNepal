import { formatScore } from '../lib/format'

interface AttackScoreProps {
  score: number
  threshold?: number | null
}

/**
 * The model's attack score (1 − score of the Normal class). It is uncalibrated: 0.9 does not
 * mean a 90% chance of an attack, so it is drawn as a bar against the alert threshold.
 */
export function AttackScore({ score, threshold }: AttackScoreProps) {
  const pct = Math.max(0, Math.min(1, score)) * 100
  return (
    <span
      className="inline-flex items-center gap-2"
      title="Uncalibrated model score, not a probability"
    >
      <span className="font-mono text-sm tabular-nums">{formatScore(score)}</span>
      <span aria-hidden="true" className="relative h-1.5 w-16 rounded bg-slate-200">
        <span
          className="absolute inset-y-0 left-0 rounded bg-slate-600"
          style={{ width: `${pct}%` }}
        />
        {threshold != null && (
          <span
            className="absolute -top-0.5 h-2.5 w-0.5 bg-red-600"
            style={{ left: `${Math.max(0, Math.min(1, threshold)) * 100}%` }}
          />
        )}
      </span>
    </span>
  )
}
