/**
 * Category colors for tag and bucket pills. Both kinds of key are opaque — tags
 * are arbitrary strings and buckets come from a source-defined taxonomy — so no
 * key is ever hardcoded here.
 *
 * Arbitrary tags get a hue by hashing, which spreads them and is stable per
 * string. Taxonomy buckets get one by position (`bucketColor`), since a round
 * shows them side by side and they have to stay distinct.
 */

/** The category ramp, as CSS custom-property names (defined in `style.css`). */
export const CATEGORY_TOKENS = [
  '--color-cat-1',
  '--color-cat-2',
  '--color-cat-3',
  '--color-cat-4',
  '--color-cat-5',
] as const

/** The same ramp as CSS color values, for anything styling an element. */
export const CATEGORY_COLORS = CATEGORY_TOKENS.map((token) => `var(${token})`)

/** Stable, well-spread string hash (djb2). */
function hash(key: string): number {
  let h = 5381
  for (let i = 0; i < key.length; i++) h = ((h << 5) + h + key.charCodeAt(i)) >>> 0
  return h
}

/** The category color for an arbitrary tag string. */
export function categoryColor(key: string): string {
  return CATEGORY_COLORS[hash(key) % CATEGORY_COLORS.length]
}

/** The goal bucket's hue: neutral, so the accent ramp only ever means "bonus". */
const GOAL_COLOR = 'var(--color-ink-muted)'

/**
 * The color for a taxonomy bucket, from its position among the round's
 * bonus-bucket keys.
 *
 * Position keeps every bucket a distinct hue up to the ramp's length, and the
 * order is stable across rounds because the server sends all its bonus buckets
 * in taxonomy order whether or not the current image has any. No key is
 * hardcoded: the goal bucket is the one *absent* from `bonusKeys`, the same
 * negative test the reducer uses. A taxonomy with more bonus buckets than the
 * ramp has colors wraps around and repeats hues.
 */
export function bucketColor(key: string, bonusKeys: readonly string[]): string {
  const i = bonusKeys.indexOf(key)
  return i < 0 ? GOAL_COLOR : CATEGORY_COLORS[i % CATEGORY_COLORS.length]
}

/** `categoryPillStyle`, for a bucket key colored by its position. */
export function bucketPillStyle(
  key: string,
  bonusKeys: readonly string[],
): { color: string; backgroundColor: string } {
  return tint(bucketColor(key, bonusKeys))
}

/**
 * Inline style for a tinted category pill: solid text over a faint fill of the
 * same hue — the correct/wrong pill look, generalized to arbitrary categories.
 */
export function categoryPillStyle(key: string): { color: string; backgroundColor: string } {
  return tint(categoryColor(key))
}

function tint(color: string): { color: string; backgroundColor: string } {
  return { color, backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)` }
}
