/**
 * Pure reducer over the `game_events` stream: `(state, event) => state`.
 *
 * All game-view state derives from replaying events in order, with no Vue or
 * socket dependency, so it's unit-testable in isolation (mirrors the backend's
 * pure domain). The Pinia `game` store is a thin wrapper that just holds the
 * latest `GameState` and feeds batches through `reduceAll`.
 */

import type { BucketKey, GameEvent, Player, RejectReason } from '@/types/wire'

export type GameStatus = 'idle' | 'active' | 'over' | 'aborted' | 'no_image' | 'image_error'

/** The picture on display — no answer-revealing fields (see `image_started`). */
export interface RoundImage {
  id: string
  thumb_url: string
  full_url: string
}

/** Attribution, known only once the round ends (`image_revealed`). */
export interface Attribution {
  artists: string[]
  source_url: string | null
  page_url: string
}

export interface GameOverResult {
  win: boolean
  winners: Player[]
  standings: Player[]
  unguessed_tags: string[]
}

/** One entry in the ordered guess feed; `seq` is a stable key for rendering. */
export type FeedEntry = FeedInput & { seq: number }

type FeedInput =
  | { kind: 'correct'; player: string; guess: string; tag_type: BucketKey }
  | { kind: 'wrong'; player: string; guess: string; closeness: number }
  | { kind: 'timeout'; player: string }
  | { kind: 'rejected'; guess: string; reason: RejectReason }
  | { kind: 'eliminated'; player: string }

export interface GameState {
  status: GameStatus
  image: RoundImage | null
  reveal: Attribution | null
  /** uuid of the player whose turn it is, or null when no game is running. */
  activePlayerUuid: string | null
  /** Goal-bucket size and how many of it are still unguessed. */
  goalTagCount: number
  goalRemaining: number
  /** Remaining count per bonus bucket, keyed by opaque bucket key. */
  bonusCounts: Record<BucketKey, number>
  /** Players seen so far this round, keyed by uuid (latest score snapshot). */
  players: Record<string, Player>
  eliminated: string[]
  feed: FeedEntry[]
  feedSeq: number
  over: GameOverResult | null
  /** The query that came back empty, when `status === 'no_image'`. */
  noImageQuery: string[] | null
}

export function initialGameState(): GameState {
  return {
    status: 'idle',
    image: null,
    reveal: null,
    activePlayerUuid: null,
    goalTagCount: 0,
    goalRemaining: 0,
    bonusCounts: {},
    players: {},
    eliminated: [],
    feed: [],
    feedSeq: 0,
    over: null,
    noImageQuery: null,
  }
}

export function reduce(prev: GameState, event: GameEvent): GameState {
  switch (event.type) {
    case 'image_started':
      // A fresh picture opens a fresh round; drop any prior game's state.
      return {
        ...initialGameState(),
        status: 'active',
        image: { id: event.id, thumb_url: event.thumb_url, full_url: event.full_url },
      }

    case 'game_started': {
      // Seed the whole roster so the scoreboard is complete from the first turn
      // and spectators (room members not in it) are known immediately.
      const players = { ...prev.players }
      for (const p of event.players) recordPlayer(players, p)
      return {
        ...prev,
        status: 'active',
        activePlayerUuid: event.first_player.uuid,
        goalTagCount: event.tag_count,
        goalRemaining: event.tag_count,
        bonusCounts: { ...event.bonus_counts },
        players,
      }
    }

    case 'turn_started': {
      const players = { ...prev.players }
      recordPlayer(players, event.player)
      return { ...prev, activePlayerUuid: event.player.uuid, players }
    }

    case 'correct_guess': {
      const players = { ...prev.players }
      recordPlayer(players, event.player)
      // A goal-bucket key isn't in bonus_counts; that's how we tell them apart
      // without naming any bucket (taxonomy is source-defined, not hardcoded).
      // `Object.hasOwn`, not `in`: keys are opaque, and `in` would match
      // prototype members like "constructor"/"toString".
      const isBonus = Object.hasOwn(prev.bonusCounts, event.tag_type)
      return {
        ...prev,
        players,
        bonusCounts: isBonus
          ? { ...prev.bonusCounts, [event.tag_type]: event.remaining }
          : prev.bonusCounts,
        goalRemaining: isBonus ? prev.goalRemaining : event.remaining,
        ...withFeed(prev, {
          kind: 'correct',
          player: event.player.name,
          guess: event.guess,
          tag_type: event.tag_type,
        }),
      }
    }

    case 'wrong_guess': {
      const players = { ...prev.players }
      recordPlayer(players, event.player)
      return {
        ...prev,
        players,
        ...withFeed(prev, {
          kind: 'wrong',
          player: event.player.name,
          guess: event.guess,
          closeness: event.closeness,
        }),
      }
    }

    case 'timeout': {
      const players = { ...prev.players }
      recordPlayer(players, event.player)
      return {
        ...prev,
        players,
        ...withFeed(prev, { kind: 'timeout', player: event.player.name }),
      }
    }

    case 'guess_rejected':
      return {
        ...prev,
        ...withFeed(prev, { kind: 'rejected', guess: event.guess, reason: event.reason }),
      }

    case 'player_eliminated': {
      const players = { ...prev.players }
      recordPlayer(players, event.player)
      return {
        ...prev,
        players,
        eliminated: prev.eliminated.includes(event.player.uuid)
          ? prev.eliminated
          : [...prev.eliminated, event.player.uuid],
        ...withFeed(prev, { kind: 'eliminated', player: event.player.name }),
      }
    }

    case 'game_over': {
      const players = { ...prev.players }
      for (const p of event.standings) recordPlayer(players, p)
      return {
        ...prev,
        status: 'over',
        activePlayerUuid: null,
        players,
        over: {
          win: event.win,
          winners: event.winners,
          standings: event.standings,
          unguessed_tags: event.unguessed_tags,
        },
      }
    }

    case 'game_aborted':
      return { ...prev, status: 'aborted', activePlayerUuid: null }

    case 'image_revealed':
      return {
        ...prev,
        reveal: {
          artists: event.artists,
          source_url: event.source_url,
          page_url: event.page_url,
        },
      }

    case 'no_image':
      // A failed new round starts clean — don't leave the prior game's picture,
      // scoreboard, or feed showing under a "no image" status.
      return { ...initialGameState(), status: 'no_image', noImageQuery: event.query }

    case 'image_error':
      return { ...initialGameState(), status: 'image_error' }

    default:
      return unhandled(prev, event)
  }
}

/** Fold an ordered batch (the shape `game_events` arrives in) into the state. */
export function reduceAll(prev: GameState, events: GameEvent[]): GameState {
  return events.reduce(reduce, prev)
}

function recordPlayer(players: Record<string, Player>, player: Player): void {
  players[player.uuid] = player
}

function withFeed(prev: GameState, entry: FeedInput): Pick<GameState, 'feed' | 'feedSeq'> {
  const seq = prev.feedSeq + 1
  return { feed: [...prev.feed, { seq, ...entry }], feedSeq: seq }
}

// `event: never` makes this a compile-time exhaustiveness guard — a new event
// type breaks the build here — while staying runtime-safe on unknown input.
function unhandled(prev: GameState, _event: never): GameState {
  return prev
}
