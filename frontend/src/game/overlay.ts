/**
 * Turns a feed entry into the hero card the guess overlay shows over the image.
 *
 * Pure, like the reducer it reads from: no Vue, no store, no timers — those live
 * in `GuessOverlay.vue`. All the wording and tone decisions are here so they're
 * testable without mounting anything.
 */

import type { FeedEntry } from '@/game/reducer'
import type { BucketKey, RejectReason } from '@/types/wire'

/** Drives the card's color and iconography. */
export type CardTone = 'correct' | 'wrong' | 'near' | 'out' | 'muted'

export interface OverlayCard {
  seq: number
  tone: CardTone
  /** Name of the player this card is about; null for guesses nobody is blamed for. */
  player: string | null
  /** The canonical tag, or a sentence for the entries that aren't a tag. */
  headline: string
  /** Set only when the server resolved the guess to something else. */
  asTyped?: string
  /** The line under the headline; empty when the tone alone says it. */
  detail: string
  /** Present on entries that cost a strike — `used` X marks out of `limit`. */
  strikes?: { used: number; limit: number }
  /** Correct guesses only, for the bucket-colored pill. */
  bucket?: BucketKey
}

const REJECT: Record<RejectReason, string> = {
  already_guessed: 'already found',
  already_wrong: 'already tried',
  default_tag: 'freebie tag',
  rating_tag: 'rating tag',
  ignored_tag: 'not guessable',
}

/**
 * Cards for the feed entries newer than `sinceSeq`, in order.
 *
 * Takes the whole feed rather than just the new slice so a card can be judged
 * against what came before it — which is what lets the elimination that follows
 * a third strike be dropped as a repeat.
 */
export function overlayCards(
  feed: readonly FeedEntry[],
  strikeLimit: number,
  sinceSeq = 0,
): OverlayCard[] {
  const cards: OverlayCard[] = []
  for (const [i, entry] of feed.entries()) {
    if (entry.seq <= sinceSeq) continue
    if (repeatsElimination(feed[i - 1], entry, strikeLimit)) continue
    const card = overlayCard(entry, strikeLimit)
    if (card) cards.push(card)
  }
  return cards
}

/**
 * Whether this elimination is already covered by the strike right before it.
 *
 * A player's last strike and their elimination always arrive together, and the
 * strike's own card already reads as the elimination — same player, out tone, a
 * full row of X marks. Showing both says one thing twice, at the most charged
 * moment of the round.
 */
function repeatsElimination(
  previous: FeedEntry | undefined,
  entry: FeedEntry,
  strikeLimit: number,
): boolean {
  if (entry.kind !== 'eliminated' || previous === undefined) return false
  if (previous.kind !== 'wrong' && previous.kind !== 'timeout') return false
  return previous.player === entry.player && previous.strike >= strikeLimit
}

/**
 * The card for a feed entry, or null when it doesn't warrant the overlay.
 *
 * Freebies are the only skip: they arrive as one batch at the start of a round,
 * so showing them would open every game with a flurry of cards nobody guessed.
 * They stay in the rail feed.
 */
export function overlayCard(entry: FeedEntry, strikeLimit: number): OverlayCard | null {
  const base = { seq: entry.seq }

  switch (entry.kind) {
    case 'freebie':
      return null

    case 'correct':
      return {
        ...base,
        tone: 'correct',
        player: entry.player,
        headline: entry.guess,
        asTyped: entry.asTyped,
        // Taxonomy keys are already plural ("tags", "artists"), so they read as
        // a label unchanged — never suffix them.
        detail: entry.remaining === 0 ? `all ${entry.tagType} found` : `${entry.remaining} left`,
        bucket: entry.tagType,
      }

    case 'wrong':
      return {
        ...base,
        // The strike that eliminates reads as elimination, not as another miss.
        tone: entry.strike >= strikeLimit ? 'out' : 'wrong',
        player: entry.player,
        headline: entry.guess,
        asTyped: entry.asTyped,
        detail: strikeText(entry.strike, strikeLimit),
        strikes: { used: entry.strike, limit: strikeLimit },
      }

    case 'near_miss':
      return {
        ...base,
        tone: 'near',
        player: entry.player,
        headline: entry.guess,
        asTyped: entry.asTyped,
        detail: `so close · ${entry.closeness}% · free retry`,
      }

    case 'timeout':
      return {
        ...base,
        tone: entry.strike >= strikeLimit ? 'out' : 'wrong',
        player: entry.player,
        headline: 'ran out of time',
        detail: strikeText(entry.strike, strikeLimit),
        strikes: { used: entry.strike, limit: strikeLimit },
      }

    case 'eliminated':
      return {
        ...base,
        tone: 'out',
        player: entry.player,
        headline: 'is out',
        detail: '',
      }

    case 'rejected':
      return {
        ...base,
        tone: 'muted',
        player: null,
        headline: entry.guess,
        asTyped: entry.asTyped,
        detail: REJECT[entry.reason],
      }
  }
}

function strikeText(used: number, limit: number): string {
  return used >= limit ? 'eliminated' : `strike ${used} of ${limit}`
}
