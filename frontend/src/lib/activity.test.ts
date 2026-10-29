import { describe, expect, it } from 'vitest'

import { fillDays } from './activity'

describe('fillDays', () => {
  it('fills days without alerts with zero, ending on the generation day (UTC)', () => {
    const days = fillDays(
      [
        { day: '2026-10-26T00:00:00Z', count: 4 },
        { day: '2026-10-28T00:00:00Z', count: 2 },
      ],
      '2026-10-28T23:30:00Z',
      4,
    )
    expect(days.map((d) => [d.day, d.count])).toEqual([
      ['2026-10-25', 0],
      ['2026-10-26', 4],
      ['2026-10-27', 0],
      ['2026-10-28', 2],
    ])
  })
})
