import { afterEach, describe, expect, it, vi } from 'vitest'

import { log } from '@/lib/logger'

describe('logger', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
  })

  it('gates debug on DEV but always warns', () => {
    const debug = vi.spyOn(console, 'debug').mockImplementation(() => {})
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    vi.stubEnv('DEV', false)
    log.debug('quiet')
    expect(debug).not.toHaveBeenCalled() // silenced in a production build

    vi.stubEnv('DEV', true)
    log.debug('loud')
    expect(debug).toHaveBeenCalledWith('[derpigame]', 'loud')

    log.warn('always') // warn/error fire regardless of DEV
    expect(warn).toHaveBeenCalledWith('[derpigame]', 'always')
  })
})
