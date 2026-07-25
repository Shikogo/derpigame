/**
 * What a celebration is made of, as `canvas-confetti` calls.
 *
 * The motion is the library's — we own only the recipe: which shots go up, when,
 * from where. Keeping that here as plain data means the rule ("a win is one
 * pop, a sweep is fireworks, both stack") stays unit-testable without a canvas.
 */

import type { Options } from 'canvas-confetti'

export type CelebrationKind = 'winner' | 'sweep'

/** One `confetti()` call and how long after the celebration starts it fires. */
export interface Shot {
  at: number
  options: Options
}

export interface ViewSize {
  width: number
  height: number
}

/** The knobs this recipe sets; everything else is library default. */
interface ConfettiTuning {
  /** Pieces per cannon barrel (a firework shell throws proportionally fewer). */
  particleCount: number
  /** Cone width, degrees. */
  spread: number
  /** Launch speed. Scaled by viewport height so a big window isn't timid. */
  startVelocity: number
  /** Per-frame velocity retention: lower stops the pieces sooner — the pop. */
  decay: number
  gravity: number
  /** Paper size multiplier. */
  scalar: number
  /** How long a piece lives, in frames. */
  ticks: number
}

const TUNING: ConfettiTuning = {
  particleCount: 55,
  spread: 62,
  // Reach is roughly `startVelocity / (1 - decay)` px, so these two together are
  // what decide whether a corner cannon crosses the screen or dies beside it.
  startVelocity: 65,
  decay: 0.94,
  gravity: 1,
  scalar: 1,
  ticks: 280,
}

/** Just off the floor, so the whole arc is on screen rather than half of it. */
const CANNON_Y = 0.92

/** The viewport the tuning is written against; taller windows throw harder. */
const REFERENCE_HEIGHT = 900

export function viewScale(view: ViewSize): number {
  return Math.min(Math.max(view.height / REFERENCE_HEIGHT, 0.8), 1.6)
}

/** Both barrels at the same instant — a bang, not a stream. */
function cannons(view: ViewSize): Shot[] {
  // `ConfettiTuning` is named after the library's own options, so it spreads
  // straight in and only the overrides need spelling out.
  const shared: Options = { ...TUNING, startVelocity: TUNING.startVelocity * viewScale(view) }
  return [
    { at: 0, options: { ...shared, angle: 60, origin: { x: 0, y: CANNON_Y } } },
    { at: 0, options: { ...shared, angle: 120, origin: { x: 1, y: CANNON_Y } } },
  ]
}

/**
 * Shells going off around the upper screen, each throwing the full circle.
 * Unlike the cannons these are meant to land one after another — separate
 * events rather than one salvo smeared out.
 */
function fireworks(view: ViewSize, random: () => number, start: number): Shot[] {
  const scale = viewScale(view)
  return Array.from({ length: 10 }, (_, i) => ({
    at: start + i * 340,
    options: {
      ...TUNING,
      particleCount: Math.round(TUNING.particleCount * 0.75),
      spread: 360,
      startVelocity: TUNING.startVelocity * 0.5 * scale,
      origin: { x: 0.12 + random() * 0.76, y: 0.12 + random() * 0.38 },
    },
  }))
}

/**
 * The shots for a celebration, composed from what there is to celebrate: a
 * `winner` is one cannon pop, a `sweep` is fireworks. Winning the round the room
 * swept earns both — shot first, shells behind it.
 */
export function celebration(
  kinds: readonly CelebrationKind[],
  view: ViewSize,
  random: () => number = Math.random,
): Shot[] {
  const won = kinds.includes('winner')
  const shots = won ? cannons(view) : []
  if (!kinds.includes('sweep')) return shots
  // Shells hold back for the shot when there is one, and open promptly when
  // there isn't — nobody should watch an empty screen for a third of a second.
  return [...shots, ...fireworks(view, random, won ? 340 : 120)]
}
