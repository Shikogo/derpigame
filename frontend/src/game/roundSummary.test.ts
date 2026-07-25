import { describe, expect, it } from 'vitest'

import { type GameState, initialGameState, reduceAll } from './reducer'
import { foundTags, missedGroups, suggestedTags } from './roundSummary'
import type { GameEvent, Player } from '@/types/wire'

const alice: Player = { uuid: 'a', name: 'Alice', score: 0, wrong_guesses: 0 }
const bob: Player = { uuid: 'b', name: 'Bob', score: 0, wrong_guesses: 0 }

/** A finished round: two freebies, a mix of guesses, then game over. */
function playedRound(): GameState {
  const events: GameEvent[] = [
    {
      type: 'image_started',
      id: '42',
      thumb_url: 't.jpg',
      full_url: 'f.jpg',
      source: 'derpibooru',
    },
    {
      type: 'game_started',
      first_player: alice,
      players: [alice, bob],
      tag_count: 3,
      bonus_counts: { artists: 1, ocs: 1 },
      freebie_tags: ['safe'],
      turn_seconds: 30,
      elimination_threshold: 3,
    },
    {
      type: 'correct_guess',
      player: { ...alice, score: 1 },
      guess: 'pony',
      tag_type: 'tags',
      remaining: 2,
    },
    { type: 'wrong_guess', player: { ...bob, wrong_guesses: 1 }, guess: 'nope', wrong_count: 1 },
    { type: 'near_miss', player: bob, guess: 'ponee', closeness: 88 },
    { type: 'timeout', player: bob, wrong_count: 2 },
    { type: 'guess_rejected', guess: 'pony', reason: 'already_guessed' },
    { type: 'player_eliminated', player: bob },
    {
      type: 'wrong_guess',
      player: { ...alice, wrong_guesses: 1 },
      guess: 'unicorn',
      wrong_count: 1,
    },
    {
      type: 'correct_guess',
      player: { ...alice, score: 2 },
      guess: 'oc:nyx',
      tag_type: 'ocs',
      remaining: 0,
    },
    {
      type: 'game_over',
      win: false,
      winners: [alice],
      standings: [alice, bob],
      win_counts: [],
      unguessed: { tags: ['rarity', 'mare'], artists: ['artist:foo'] },
    },
  ]
  return reduceAll(initialGameState(), events)
}

describe('foundTags', () => {
  it('keeps correct guesses and freebies, in feed order', () => {
    expect(foundTags(playedRound())).toEqual([
      { tag: 'safe', bucket: null, player: null },
      { tag: 'pony', bucket: 'tags', player: 'Alice' },
      { tag: 'oc:nyx', bucket: 'ocs', player: 'Alice' },
    ])
  })

  it('excludes everything that is not a correct guess', () => {
    const tags = foundTags(playedRound()).map((t) => t.tag)
    // wrong, near-miss, timeout, rejection and elimination all produce feed rows
    expect(tags).not.toContain('nope')
    expect(tags).not.toContain('ponee')
    expect(tags).toHaveLength(3)
  })

  it('is empty for a round nobody scored in', () => {
    expect(foundTags(initialGameState())).toEqual([])
  })
})

describe('missedGroups', () => {
  it('groups by bucket in server order, tags alphabetical within a bucket', () => {
    expect(missedGroups(playedRound())).toEqual([
      { bucket: 'tags', tags: ['mare', 'rarity'] },
      { bucket: 'artists', tags: ['artist:foo'] },
    ])
  })

  it('drops buckets the room cleared out', () => {
    const buckets = missedGroups(playedRound()).map((g) => g.bucket)
    expect(buckets).not.toContain('ocs') // the only oc was guessed
  })

  it('is empty while a round is still running', () => {
    expect(missedGroups(initialGameState())).toEqual([])
  })

  it('does not mutate the state it reads', () => {
    const state = playedRound()
    missedGroups(state)
    expect(state.unguessed.tags).toEqual(['rarity', 'mare']) // sorted a copy
  })
})

describe('suggestedTags', () => {
  it('keeps wrong guesses with their guesser, in feed order', () => {
    expect(suggestedTags(playedRound())).toEqual([
      { tag: 'nope', player: 'Bob' },
      { tag: 'unicorn', player: 'Alice' },
    ])
  })

  it('excludes near misses — those are typos of a tag the image already has', () => {
    expect(suggestedTags(playedRound()).map((t) => t.tag)).not.toContain('ponee')
  })

  it('excludes correct guesses, freebies, timeouts and rejections', () => {
    const tags = suggestedTags(playedRound()).map((t) => t.tag)
    expect(tags).not.toContain('pony')
    expect(tags).not.toContain('safe')
    expect(tags).toHaveLength(2)
  })

  it('is empty for a round with no wrong guesses', () => {
    expect(suggestedTags(initialGameState())).toEqual([])
  })
})
