import { describe, expect, it } from 'vitest'

import { type GameState, initialGameState, reduce, reduceAll } from './reducer'
import type { GameEvent, Player } from '@/types/wire'

const alice: Player = { uuid: 'a', name: 'Alice', score: 0, wrong_guesses: 0 }
const bob: Player = { uuid: 'b', name: 'Bob', score: 0, wrong_guesses: 0 }

function player(base: Player, over: Partial<Player>): Player {
  return { ...base, ...over }
}

/** The opening batch: image, then game_started, then the first turn. */
function openedGame(freebieTags: string[] = []): GameState {
  const events: GameEvent[] = [
    { type: 'image_started', id: '42', thumb_url: 't.jpg', full_url: 'f.jpg' },
    {
      type: 'game_started',
      first_player: alice,
      players: [alice],
      tag_count: 3,
      bonus_counts: { artists: 1 },
      freebie_tags: freebieTags,
      turn_seconds: 30,
    },
    { type: 'turn_started', player: alice },
  ]
  return reduceAll(initialGameState(), events)
}

describe('reduce', () => {
  it('image_started sets the picture and hides answer fields', () => {
    const s = reduce(initialGameState(), {
      type: 'image_started',
      id: '42',
      thumb_url: 't.jpg',
      full_url: 'f.jpg',
    })
    expect(s.status).toBe('active')
    expect(s.image).toEqual({ id: '42', thumb_url: 't.jpg', full_url: 'f.jpg' })
    // no artists / source / page leaked mid-game
    expect(s.reveal).toBeNull()
    expect(Object.keys(s.image ?? {})).toEqual(['id', 'thumb_url', 'full_url'])
  })

  it('image_started resets any prior round state', () => {
    const dirty = openedGame()
    const fresh = reduce(dirty, {
      type: 'image_started',
      id: '99',
      thumb_url: 't2.jpg',
      full_url: 'f2.jpg',
    })
    expect(fresh.goalRemaining).toBe(0)
    expect(fresh.bonusCounts).toEqual({})
    expect(fresh.feed).toEqual([])
    expect(fresh.players).toEqual({})
  })

  it('game_started seeds counts and the first active player', () => {
    const s = openedGame()
    expect(s.goalTagCount).toBe(3)
    expect(s.goalRemaining).toBe(3)
    expect(s.bonusCounts).toEqual({ artists: 1 })
    expect(s.activePlayerUuid).toBe('a')
  })

  it('game_started seeds the freebies into the feed', () => {
    const s = openedGame(['safe', 'mare'])
    expect(s.feed).toEqual([
      { seq: 1, kind: 'freebie', guess: 'safe' },
      { seq: 2, kind: 'freebie', guess: 'mare' },
    ])
    const guessed = reduce(s, {
      type: 'wrong_guess',
      player: player(alice, { wrong_guesses: 1 }),
      guess: 'nope',
      wrong_count: 1,
    })
    expect(guessed.feed.at(-1)).toEqual({ seq: 3, kind: 'wrong', player: 'Alice', guess: 'nope' })
  })

  it('game_started seeds the whole roster, not just the first player', () => {
    const s = reduceAll(initialGameState(), [
      { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f' },
      { type: 'game_started', first_player: alice, players: [alice, bob], tag_count: 2, bonus_counts: {}, freebie_tags: [], turn_seconds: 30 },
      { type: 'turn_started', player: alice },
    ])
    expect(Object.keys(s.players).sort()).toEqual(['a', 'b'])
    expect(s.players.b).toEqual(bob)
  })

  it('turn_started moves the active player', () => {
    const s = reduce(openedGame(), { type: 'turn_started', player: bob })
    expect(s.activePlayerUuid).toBe('b')
    expect(s.players.b).toEqual(bob)
  })

  it('turn_started bumps turnSeq even when the same player keeps the turn', () => {
    const first = reduce(openedGame(), { type: 'turn_started', player: alice })
    const second = reduce(first, { type: 'turn_started', player: alice })
    expect(second.activePlayerUuid).toBe('a')
    expect(second.turnSeq).toBe(first.turnSeq + 1)
  })

  it('a correct goal guess decrements goalRemaining, not a bonus bucket', () => {
    const s = reduce(openedGame(), {
      type: 'correct_guess',
      player: player(alice, { score: 1 }),
      guess: 'pony',
      tag_type: 'tags',
      remaining: 2,
    })
    expect(s.goalRemaining).toBe(2)
    expect(s.bonusCounts).toEqual({ artists: 1 })
    expect(s.players.a?.score).toBe(1)
    expect(s.feed).toEqual([{ seq: 1, kind: 'correct', player: 'Alice', guess: 'pony' }])
  })

  it('a correct bonus guess updates only that bucket', () => {
    const s = reduce(openedGame(), {
      type: 'correct_guess',
      player: player(alice, { score: 3 }),
      guess: 'artist:foo',
      tag_type: 'artists',
      remaining: 0,
    })
    expect(s.bonusCounts).toEqual({ artists: 0 })
    expect(s.goalRemaining).toBe(3) // untouched
  })

  it('wrong_guess and timeout record the player and feed the entry', () => {
    let s = reduce(openedGame(), {
      type: 'wrong_guess',
      player: player(alice, { wrong_guesses: 1 }),
      guess: 'nope',
      wrong_count: 1,
    })
    s = reduce(s, { type: 'timeout', player: player(alice, { wrong_guesses: 2 }), wrong_count: 2 })
    expect(s.players.a?.wrong_guesses).toBe(2)
    expect(s.feed.map((f) => f.kind)).toEqual(['wrong', 'timeout'])
  })

  it('near_miss feeds the guess with its closeness, no strike', () => {
    const s = reduce(openedGame(), {
      type: 'near_miss',
      player: alice,
      guess: 'applejck',
      closeness: 94,
    })
    expect(s.feed).toEqual([
      { seq: 1, kind: 'near_miss', player: 'Alice', guess: 'applejck', closeness: 94 },
    ])
    expect(s.players.a?.wrong_guesses).toBe(0)
  })

  it('guess_rejected only feeds, never touches scores', () => {
    const s = reduce(openedGame(), { type: 'guess_rejected', guess: 'safe', reason: 'rating_tag' })
    expect(s.feed).toEqual([{ seq: 1, kind: 'rejected', guess: 'safe', reason: 'rating_tag' }])
    expect(s.players.a?.score).toBe(0)
  })

  it('player_eliminated marks the player once', () => {
    let s = reduce(openedGame(), { type: 'player_eliminated', player: alice })
    s = reduce(s, { type: 'player_eliminated', player: alice })
    expect(s.eliminated).toEqual(['a'])
    expect(s.feed).toHaveLength(2) // still feeds each time
  })

  it('game_over records the result and clears the active turn', () => {
    const s = reduce(openedGame(), {
      type: 'game_over',
      win: false,
      winners: [],
      standings: [player(alice, { score: 2 }), bob],
      unguessed_tags: ['rare'],
    })
    expect(s.status).toBe('over')
    expect(s.activePlayerUuid).toBeNull()
    expect(s.over?.unguessed_tags).toEqual(['rare'])
    expect(s.players.a?.score).toBe(2) // standings backfill players
  })

  it('image_revealed attribution surfaces on game_over', () => {
    let s = reduce(openedGame(), {
      type: 'game_over',
      win: true,
      winners: [alice],
      standings: [alice],
      unguessed_tags: [],
    })
    s = reduce(s, {
      type: 'image_revealed',
      artists: ['foo'],
      source_url: 'https://src',
      page_url: 'https://derpi/42',
    })
    expect(s.status).toBe('over')
    expect(s.reveal).toEqual({ artists: ['foo'], source_url: 'https://src', page_url: 'https://derpi/42' })
  })

  it('image_revealed attribution also surfaces on an aborted round', () => {
    let s = reduce(openedGame(), { type: 'game_aborted' })
    s = reduce(s, {
      type: 'image_revealed',
      artists: ['foo'],
      source_url: null,
      page_url: 'https://derpi/42',
    })
    expect(s.status).toBe('aborted')
    expect(s.reveal?.source_url).toBeNull()
    expect(s.reveal?.page_url).toBe('https://derpi/42')
  })

  it('game_snapshot rebuilds a live round for a (re)joining client', () => {
    const s = reduce(initialGameState(), {
      type: 'game_snapshot',
      image: { id: '7', thumb_url: 't', full_url: 'f' },
      players: [player(alice, { score: 2 }), player(bob, { score: 1, wrong_guesses: 1 })],
      active_player: bob,
      freebie_tags: ['safe', 'mare'],
      tag_count: 4,
      goal_remaining: 1,
      bonus_counts: { artists: 2 },
      eliminated: ['c'],
      turn_seconds: 20,
    })
    expect(s.status).toBe('active')
    expect(s.feed).toEqual([
      { seq: 1, kind: 'freebie', guess: 'safe' },
      { seq: 2, kind: 'freebie', guess: 'mare' },
    ])
    expect(s.turnSeconds).toBe(20)
    expect(s.image).toEqual({ id: '7', thumb_url: 't', full_url: 'f' })
    expect(s.activePlayerUuid).toBe('b')
    expect(s.goalTagCount).toBe(4)
    expect(s.goalRemaining).toBe(1)
    expect(s.bonusCounts).toEqual({ artists: 2 })
    expect(s.players.a?.score).toBe(2)
    expect(s.eliminated).toEqual(['c'])
  })

  it('no_image and image_error set their status', () => {
    expect(reduce(initialGameState(), { type: 'no_image', query: ['x'] })).toMatchObject({
      status: 'no_image',
      noImageQuery: ['x'],
    })
    expect(reduce(initialGameState(), { type: 'image_error' }).status).toBe('image_error')
  })

  it('no_image and image_error clear the prior round, not just the status', () => {
    const finished = reduce(openedGame(), {
      type: 'game_over',
      win: true,
      winners: [alice],
      standings: [alice],
      unguessed_tags: [],
    })
    const empty = reduce(finished, { type: 'no_image', query: ['x'] })
    expect(empty).toMatchObject({ image: null, over: null, reveal: null, feed: [], players: {} })
    const errored = reduce(finished, { type: 'image_error' })
    expect(errored).toMatchObject({ image: null, over: null, feed: [] })
  })

  it('a bucket key colliding with an Object prototype member stays a goal guess', () => {
    // opaque keys must not be classified via `in`; "constructor" ∈ every object
    const s = reduce(openedGame(), {
      type: 'correct_guess',
      player: player(alice, { score: 1 }),
      guess: 'x',
      tag_type: 'constructor',
      remaining: 2,
    })
    expect(s.goalRemaining).toBe(2) // treated as the goal bucket, decremented
    expect(s.bonusCounts).toEqual({ artists: 1 }) // untouched
  })

  it('does not mutate the previous state', () => {
    const prev = openedGame()
    const snapshot = JSON.stringify(prev)
    reduce(prev, { type: 'turn_started', player: bob })
    expect(JSON.stringify(prev)).toBe(snapshot)
  })
})
