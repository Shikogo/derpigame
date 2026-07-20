/**
 * The end-of-round recap, derived from a finished `GameState`.
 *
 * Three views of the round: the image's tags the room got (replayed out of the
 * feed, so a rejoin gets them too), the ones it didn't (the answer key the
 * server sends once the round is over), and the wrong guesses — tags the image
 * doesn't carry, which are worth a look as ones it arguably should. Pure like
 * the reducer — no Vue, no socket — so `RoundSummary.vue` stays a rendering
 * shell.
 */

import type { GameState } from '@/game/reducer'
import type { BucketKey } from '@/types/wire'

/** A tag the room ended up with. Freebies were given, so they have no guesser. */
export interface FoundTag {
  tag: string
  /** The taxonomy bucket it landed in, or null for a freebie (never classified). */
  bucket: BucketKey | null
  player: string | null
}

export interface MissedGroup {
  bucket: BucketKey
  tags: string[]
}

/** A wrong guess, read as a tag the image may be missing. */
export interface SuggestedTag {
  tag: string
  player: string
}

/** Tags the room got, in the order they turned up. */
export function foundTags(state: GameState): FoundTag[] {
  const found: FoundTag[] = []
  for (const entry of state.feed) {
    if (entry.kind === 'correct') {
      found.push({ tag: entry.guess, bucket: entry.tagType, player: entry.player })
    } else if (entry.kind === 'freebie') {
      found.push({ tag: entry.guess, bucket: null, player: null })
    }
  }
  return found
}

/**
 * Tags nobody got, grouped by bucket. Bucket order is the server's (goal bucket
 * first); tags within a bucket are alphabetical, since guess order says nothing
 * about the ones that were never guessed.
 */
export function missedGroups(state: GameState): MissedGroup[] {
  return Object.entries(state.unguessed)
    .filter(([, tags]) => tags.length)
    .map(([bucket, tags]) => ({ bucket, tags: [...tags].sort() }))
}

/**
 * Wrong guesses, in the order they were made — candidates for tagging the image
 * with upstream. Near misses are left out: those fuzzy-matched a tag the image
 * already has, so they're typos rather than suggestions. The domain only counts
 * a guess wrong once (a repeat is rejected), so these are already unique.
 */
export function suggestedTags(state: GameState): SuggestedTag[] {
  const suggested: SuggestedTag[] = []
  for (const entry of state.feed) {
    if (entry.kind === 'wrong') {
      suggested.push({ tag: entry.guess, player: entry.player })
    }
  }
  return suggested
}
