import { describe, expect, it } from 'vitest'

import { DEFAULT_TUNING, celebration, viewScale } from '@/lib/confetti'

const view = { width: 1920, height: 900 }

describe('celebration', () => {
  it('fires a win exactly once: both barrels, same instant, bottom corners', () => {
    const shots = celebration(['winner'], view)

    // The regression: staggered follow-up waves turn the bang into a stream.
    expect(shots.every((s) => s.at === 0)).toBe(true)
    expect(shots.map((s) => s.options.origin!.x)).toEqual([0, 1])
    expect(shots.every((s) => s.options.origin!.y! > 0.8)).toBe(true) // down at the floor
    // Aimed inward and up: canvas-confetti measures degrees anticlockwise from
    // due right, so the left barrel leans right of vertical and the right one left.
    expect(shots.map((s) => s.options.angle)).toEqual([60, 120])
  })

  it('gives a sweep fireworks only: in-frame shells, spaced out, full circle', () => {
    const shells = celebration(['sweep'], view)

    expect(shells.some((s) => s.options.spread !== 360)).toBe(false) // no cannons in it
    for (const shell of shells) {
      expect(shell.options.spread).toBe(360)
      expect(shell.options.origin!.y).toBeGreaterThan(0)
      expect(shell.options.origin!.y).toBeLessThan(0.6)
    }
    // Spaced out, so they land as separate events rather than one salvo.
    expect(new Set(shells.map((s) => s.at)).size).toBe(shells.length)
  })

  it('leads with the shot and holds the shells back when you won the sweep', () => {
    const cannons = celebration(['winner'], view)
    const both = celebration(['winner', 'sweep'], view)
    const shells = both.slice(cannons.length)

    expect(both.slice(0, cannons.length)).toEqual(cannons)
    expect(shells).toHaveLength(celebration(['sweep'], view).length)
    expect(shells[0].at).toBeGreaterThan(celebration(['sweep'], view)[0].at)
  })

  it('celebrates nothing when there is nothing to celebrate', () => {
    expect(celebration([], view)).toEqual([])
  })

  it('scatters the fireworks with the randomness it is handed', () => {
    const left = celebration(['sweep'], view, DEFAULT_TUNING, () => 0)
    const right = celebration(['sweep'], view, DEFAULT_TUNING, () => 1)

    expect(left.at(-1)!.options.origin!.x!).toBeLessThan(right.at(-1)!.options.origin!.x!)
  })

  it('throws harder on a taller viewport, without adding pieces', () => {
    const [small] = celebration(['winner'], view)
    const [large] = celebration(['winner'], { width: 2560, height: 1400 })

    expect(viewScale({ width: 2560, height: 1400 })).toBeGreaterThan(1)
    expect(large.options.startVelocity!).toBeGreaterThan(small.options.startVelocity!)
    expect(large.options.particleCount).toBe(small.options.particleCount)
  })

  it('takes its knobs from the tuning it is handed', () => {
    const [tuned] = celebration(['winner'], view, {
      ...DEFAULT_TUNING,
      particleCount: 20,
      scalar: 3,
    })

    expect(tuned.options.particleCount).toBe(20)
    expect(tuned.options.scalar).toBe(3)
  })
})
