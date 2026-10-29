import { describe, expect, it } from 'vitest'

import { safeNextPath } from './navigation'

describe('safeNextPath', () => {
  it.each([
    ['/alerts?x=1', '/alerts?x=1'],
    ['/incidents/4', '/incidents/4'],
    [null, '/'],
    ['', '/'],
    ['https://evil.example', '/'],
    ['//evil.example', '/'],
    ['/\\evil.example', '/'],
    ['/login?next=/x', '/'],
  ])('%s -> %s', (input, expected) => {
    expect(safeNextPath(input)).toBe(expected)
  })
})
