/**
 * Category colors for tag/bucket pills. Bucket and tag-type keys are opaque
 * (source-defined taxonomy), so we assign a color deterministically by hashing
 * the key — the same key always gets the same hue, with no key hardcoded.
 */

/** The category ramp, as CSS color values (defined in `style.css`). */
export const CATEGORY_COLORS = [
  'var(--color-cat-1)',
  'var(--color-cat-2)',
  'var(--color-cat-3)',
  'var(--color-cat-4)',
  'var(--color-cat-5)',
] as const

/** Stable, well-spread string hash (djb2). */
function hash(key: string): number {
  let h = 5381
  for (let i = 0; i < key.length; i++) h = ((h << 5) + h + key.charCodeAt(i)) >>> 0
  return h
}

/** The category color for an opaque bucket / tag-type key. */
export function categoryColor(key: string): string {
  return CATEGORY_COLORS[hash(key) % CATEGORY_COLORS.length]
}

/**
 * Inline style for a tinted category pill: solid text over a faint fill of the
 * same hue — the correct/wrong pill look, generalized to arbitrary categories.
 */
export function categoryPillStyle(key: string): { color: string; backgroundColor: string } {
  const color = categoryColor(key)
  return { color, backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)` }
}
