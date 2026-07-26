/**
 * Fabricated wire payloads for the dev harnesses. Deliberately separate from
 * `src/test/factories.ts`: app code shouldn't reach into the test tree, and the
 * two want different defaults — a harness wants a room that looks played-in.
 */

import type { GameEvent, Player, RoomState } from '@/types/wire'

export const RIVAL: Player = { uuid: 'sandbox-rival', name: 'Rival', score: 4, wrong_guesses: 2 }

/** The rival as they stood at some point mid-round — every event carries one. */
const rivalAt = (wrong_guesses: number): Player => ({ ...RIVAL, wrong_guesses })

/** A lobby snapshot for a room the local player is already a member of. */
export function devRoomState(me: Player, over: Partial<RoomState> = {}): RoomState {
  return {
    room: 'DEV',
    query: [],
    nsfw: false,
    source: 'derpibooru',
    sources: [
      { key: 'derpibooru', label: 'Derpibooru' },
      { key: 'furbooru', label: 'Furbooru' },
    ],
    min_tag_count: 15,
    min_score: 10,
    rating_caps: {},
    rating_axes: [
      {
        key: 'rating',
        label: 'Rating',
        levels: ['safe', 'suggestive', 'questionable', 'explicit'],
      },
    ],
    in_progress: false,
    turn_seconds: 30,
    users: [
      { uuid: me.uuid, name: me.name, ready: true, viewing_results: false },
      { uuid: RIVAL.uuid, name: RIVAL.name, ready: true, viewing_results: false },
    ],
    history: [],
    win_counts: [],
    ...over,
  }
}

/** Opening a round: a picture, a roster, a turn — then a couple of guesses. */
export function roundInPlay(me: Player): GameEvent[] {
  return [
    {
      type: 'image_started',
      id: 'sandbox',
      thumb_url: '',
      full_url: '/viewer-test.svg',
      source: 'derpibooru',
    },
    {
      type: 'game_started',
      first_player: me,
      players: [me, rivalAt(0)],
      tag_count: 12,
      bonus_counts: { artists: 1, ocs: 2 },
      freebie_tags: ['pony', 'safe'],
      turn_seconds: 30,
      elimination_threshold: 3,
    },
    { type: 'turn_started', player: me },
    {
      type: 'correct_guess',
      player: me,
      guess: 'twilight sparkle',
      tag_type: 'tags',
      remaining: 4,
    },
    { type: 'wrong_guess', player: rivalAt(1), guess: 'rainbow dash', wrong_count: 1 },
  ]
}

/** Attribution, as the reveal at the end of any round carries it. */
const REVEAL: GameEvent = {
  type: 'image_revealed',
  artists: ['artist:somepony'],
  source_url: null,
  page_url: 'https://derpibooru.org/images/0',
}

const UNGUESSED = { tags: ['mare', 'sky', 'solo'], artists: ['artist:somepony'] }

/**
 * Ending the round on a guess, the way a real one ends: the deciding tag lands,
 * then `game_over`. The outro plays before the results panel takes over, which
 * is the transition worth watching.
 */
export function roundWon(winners: Player[], standings: Player[], win: boolean): GameEvent[] {
  return [
    {
      type: 'correct_guess',
      player: winners[0],
      guess: 'unicorn',
      tag_type: 'tags',
      remaining: 0,
    },
    {
      type: 'game_over',
      win,
      winners,
      standings,
      unguessed: win ? {} : UNGUESSED,
      win_counts: winners.map((w) => ({ uuid: w.uuid, name: w.name, wins: 2 })),
    },
    REVEAL,
  ]
}

export function roundAborted(): GameEvent[] {
  return [{ type: 'game_aborted', unguessed: UNGUESSED }, REVEAL]
}

/** A rival's guesses, one of each verdict the overlay card renders. */
export function rivalGuesses(): GameEvent[] {
  return [
    { type: 'turn_started', player: rivalAt(1) },
    {
      type: 'correct_guess',
      player: rivalAt(1),
      guess: 'princess celestia',
      tag_type: 'tags',
      remaining: 3,
    },
    { type: 'near_miss', player: rivalAt(1), guess: 'rainbowdash', closeness: 91 },
    { type: 'wrong_guess', player: rivalAt(2), guess: 'nonsense tag', wrong_count: 2 },
  ]
}
