/**
 * The wire contract, mirrored from the backend transport layer.
 *
 * Field names are snake_case to match the Python serializers exactly
 * (`app/service/serialization.py`, `app/transport/snapshots.py`,
 * `app/transport/handlers.py`) — there is no case-translation layer, so these
 * types must track those files.
 */

// --- lobby snapshot (room_state) --------------------------------------------

export interface RoomUser {
  uuid: string
  name: string
  ready: boolean
}

/**
 * One rating scale of the image source, least to most permissive. Boorus rate
 * along several independent axes (Derpibooru: sexual content and darkness) and
 * name their levels differently, so the vocabulary is server data — render the
 * controls from this, never from a hardcoded list.
 */
export interface RatingAxis {
  key: string
  label: string
  levels: string[]
}

export interface RoomState {
  room: string
  query: string[]
  nsfw: boolean
  /** Search bounds; `null` means the setting is off. `min_score: 0` is real. */
  min_tag_count: number | null
  min_score: number | null
  /** Axis key -> the most permissive level allowed; a missing key is uncapped. */
  rating_caps: Record<string, string>
  rating_axes: RatingAxis[]
  in_progress: boolean
  turn_seconds: number
  users: RoomUser[]
  history: RoundRecord[]
  win_counts: WinCount[]
}

/**
 * A finished round kept for the lobby history: its Derpibooru link and
 * attribution, plus the result. `aborted` rounds have a link worth keeping but
 * no `winners`/`standings`.
 */
export interface RoundRecord {
  page_url: string
  source_url: string | null
  thumb_url: string
  nsfw: boolean
  artists: string[]
  win: boolean
  aborted: boolean
  winners: Player[]
  standings: Player[]
}

/** Server-computed running win count for one player, most wins first in the list. */
export interface WinCount {
  uuid: string
  name: string
  wins: number
}

// --- game events (game_events channel: a batched list) ----------------------

export interface Player {
  uuid: string
  name: string
  score: number
  wrong_guesses: number
}

/** Why a guess was a no-op (never a strike). Matches the domain `RejectReason`. */
export type RejectReason =
  'already_guessed' | 'already_wrong' | 'default_tag' | 'rating_tag' | 'ignored_tag'

/**
 * A taxonomy bucket key, e.g. "tags" or "artists". The set is defined by the
 * backend's `TagTaxonomy` and varies per source (e621 adds character/species/…),
 * so it's an opaque string here — never hardcode the possible values.
 */
export type BucketKey = string

export interface GameStarted {
  type: 'game_started'
  first_player: Player
  /** The full roster for the round; room members not in it are spectators. */
  players: Player[]
  /** Goal-bucket tags — all must be guessed to win. */
  tag_count: number
  /** Namespaced bonus buckets, keyed by bucket, e.g. { artists: 1, ocs: 2 }. */
  bonus_counts: Record<BucketKey, number>
  /** The image's tags the query already gave away — free, so never scoreable. */
  freebie_tags: string[]
  turn_seconds: number
  elimination_threshold: number
}

export interface TurnStarted {
  type: 'turn_started'
  player: Player
}

export interface GuessRejected {
  type: 'guess_rejected'
  guess: string
  reason: RejectReason
  /**
   * What the player actually typed, when it differed from the canonical `guess`
   * — a bare name that resolved to a namespaced tag, or a booru alias. Absent
   * when the guess was already canonical, which is the common case.
   */
  as_typed?: string | null
}

export interface CorrectGuess {
  type: 'correct_guess'
  player: Player
  guess: string
  tag_type: BucketKey
  /** Tags left in the bucket this guess landed in. */
  remaining: number
  as_typed?: string | null
}

export interface WrongGuess {
  type: 'wrong_guess'
  player: Player
  guess: string
  wrong_count: number
  as_typed?: string | null
}

/** A guess close enough to be a free retry: no strike, the turn stays. */
export interface NearMiss {
  type: 'near_miss'
  player: Player
  guess: string
  closeness: number
  as_typed?: string | null
}

export interface Timeout {
  type: 'timeout'
  player: Player
  wrong_count: number
}

export interface PlayerEliminated {
  type: 'player_eliminated'
  player: Player
}

export interface GameOver {
  type: 'game_over'
  win: boolean
  winners: Player[]
  standings: Player[]
  /** Tags nobody got, keyed by bucket — goal bucket first, empty ones omitted. */
  unguessed: Record<BucketKey, string[]>
}

// Service-composed payloads (plain dicts, not domain events).

export interface NoImage {
  type: 'no_image'
  query: string[]
}

export interface ImageError {
  type: 'image_error'
}

export interface GameAborted {
  type: 'game_aborted'
  /** Same shape as `GameOver.unguessed` — a stopped round reveals its tags too. */
  unguessed: Record<BucketKey, string[]>
}

/** The picture to display — deliberately without any answer-revealing tags. */
export interface ImageStarted {
  type: 'image_started'
  id: string
  thumb_url: string
  full_url: string
}

/** Attribution, revealed once the image is no longer a secret (game end/abort). */
export interface ImageRevealed {
  type: 'image_revealed'
  artists: string[]
  source_url: string | null
  page_url: string
}

/**
 * Answer-safe state of a round in progress, sent only to a (re)joining socket so
 * a reload / late join can render the live game. Counts and scores only — never
 * the unguessed goal tags.
 */
export interface GameSnapshot {
  type: 'game_snapshot'
  image: { id: string; thumb_url: string; full_url: string }
  players: Player[]
  active_player: Player
  freebie_tags: string[]
  /** Original goal-bucket size (the progress denominator). */
  tag_count: number
  goal_remaining: number
  bonus_counts: Record<BucketKey, number>
  /** uuids of players already eliminated this round. */
  eliminated: string[]
  turn_seconds: number
  elimination_threshold: number
  /** Seconds left on the active turn, so a rejoining clock resumes mid-turn. */
  turn_remaining: number
  /** The round's guesses so far, in order, to rebuild the feed. */
  feed: FeedEvent[]
}

/** The events that produce a guess-feed row, and so are replayed on a rejoin. */
export type FeedEvent =
  CorrectGuess | WrongGuess | NearMiss | Timeout | GuessRejected | PlayerEliminated

export type GameEvent =
  | GameStarted
  | TurnStarted
  | GuessRejected
  | CorrectGuess
  | WrongGuess
  | NearMiss
  | Timeout
  | PlayerEliminated
  | GameOver
  | NoImage
  | ImageError
  | GameAborted
  | ImageStarted
  | ImageRevealed
  | GameSnapshot

/** Discriminator string of every game event, for exhaustive reducer switches. */
export type GameEventType = GameEvent['type']

// --- chat (social side-channel) ---------------------------------------------

export interface ChatMessage {
  name: string
  text: string
}

// --- ack callbacks (per-caller replies) -------------------------------------

export interface OkAck {
  ok: true
  /** Present on create_room / join_room. */
  room_state?: RoomState
}

export interface ErrAck {
  ok: false
  error: string
  /** Present on a not_your_turn rejection. */
  active_player?: { uuid: string; name: string }
}

export type Ack = OkAck | ErrAck

// --- client -> server payloads ----------------------------------------------

/** A query is sent as tags; the backend also accepts a comma/newline string. */
export type QueryInput = string[] | string

export interface CreateRoomPayload {
  name: string
  uuid: string
  nsfw?: boolean
  query?: QueryInput
}

export interface JoinRoomPayload {
  room: string
  name: string
  uuid: string
}

export interface SetReadyPayload {
  ready: boolean
}

/** Only the keys present are changed; omitting one leaves that setting alone. */
export interface ConfigureRoomPayload {
  query?: QueryInput
  nsfw?: boolean
  turn_seconds?: number
  min_tag_count?: number | null
  min_score?: number | null
  rating_caps?: Record<string, string>
}

export interface SubmitGuessPayload {
  guess: string
}

export interface ChatPayload {
  text: string
}
