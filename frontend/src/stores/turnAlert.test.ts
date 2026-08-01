import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import { playChime } from '@/lib/chime'
import { useGameStore } from '@/stores/game'
import { usePreferencesStore } from '@/stores/preferences'
import { useTurnAlertStore } from '@/stores/turnAlert'
import type { GameEvent, Player } from '@/types/wire'

vi.mock('@/lib/chime', () => ({ playChime: vi.fn(), primeAudio: vi.fn() }))

const p = (uuid: string): Player => ({ uuid, name: uuid, score: 0, wrong_guesses: 0 })

const openRound: GameEvent[] = [
  { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f', source: 'derpibooru' },
  {
    type: 'game_started',
    first_player: p('other'),
    players: [p('me'), p('other')],
    tag_count: 2,
    bonus_counts: {},
    freebie_tags: [],
    turn_seconds: 30,
    elimination_threshold: 3,
  },
]

describe('turnAlert store', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('derpigame:uuid', 'me') // deterministic session identity
    document.title = 'Derpigame'
    setActivePinia(createPinia())
    vi.useFakeTimers()
    // Away by default — the chime's whole reason for existing.
    vi.spyOn(document, 'hasFocus').mockReturnValue(false)
    vi.mocked(playChime).mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  /** Hand the turn to `uuid` and let the store's watcher settle. */
  async function handTo(uuid: string): Promise<void> {
    useGameStore().applyEvents([{ type: 'turn_started', player: p(uuid) }])
    await nextTick()
  }

  it('marks the tab title for my turn and clears it again', async () => {
    useTurnAlertStore()
    useGameStore().applyEvents(openRound)
    await nextTick()
    expect(document.title).toBe('Derpigame')

    await handTo('me')
    expect(document.title).toBe('▶ Your turn — Derpigame')

    await handTo('other')
    expect(document.title).toBe('Derpigame')
  })

  it('raises the banner on an arriving turn, drops it, and skips one following my own', async () => {
    const alert = useTurnAlertStore()
    useGameStore().applyEvents(openRound)
    await nextTick()
    expect(alert.justArrived).toBe(false)

    await handTo('me')
    expect(alert.justArrived).toBe(true)

    vi.advanceTimersByTime(2000)
    expect(alert.justArrived).toBe(false)

    // Solo / last player standing: the turn never left me, so it isn't news.
    await handTo('me')
    expect(alert.justArrived).toBe(false)
  })

  it('chimes when the turn arrives and I am looking elsewhere', async () => {
    useTurnAlertStore()
    useGameStore().applyEvents(openRound)
    await nextTick()
    await handTo('me')
    expect(playChime).toHaveBeenCalledTimes(1)
  })

  it('stays quiet when I am watching, when muted, and on a turn following my own', async () => {
    const prefs = usePreferencesStore()
    useTurnAlertStore()
    useGameStore().applyEvents(openRound)
    await nextTick()

    // Looking right at it — the banner has this covered.
    vi.mocked(document.hasFocus).mockReturnValue(true)
    await handTo('me')
    expect(playChime).not.toHaveBeenCalled()

    // Solo / last player standing: the turn never left me, so it isn't news.
    vi.mocked(document.hasFocus).mockReturnValue(false)
    await handTo('me')
    expect(playChime).not.toHaveBeenCalled()

    // Muted.
    prefs.setSound(false)
    await handTo('other')
    await handTo('me')
    expect(playChime).not.toHaveBeenCalled()
  })

  it('nudges once per absence, and again after I have been back', async () => {
    useTurnAlertStore()
    useGameStore().applyEvents(openRound)
    await nextTick()

    await handTo('me')
    await handTo('other')
    await handTo('me')
    // Still away, and already told once — a second chime is just noise.
    expect(playChime).toHaveBeenCalledTimes(1)

    window.dispatchEvent(new Event('focus'))
    await handTo('other')
    await handTo('me')
    expect(playChime).toHaveBeenCalledTimes(2)
  })

  it('does not fire on creation alone', async () => {
    // Mounting into a live turn is not a handoff; a real rejoin still lands one
    // because its snapshot arrives after this store exists.
    useGameStore().applyEvents([...openRound, { type: 'turn_started', player: p('me') }])
    useTurnAlertStore()
    await nextTick()

    expect(playChime).not.toHaveBeenCalled()
    expect(document.title).toBe('Derpigame')
  })
})
