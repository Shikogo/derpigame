/**
 * The "you're up" chime, synthesized rather than shipped as an audio file.
 *
 * Autoplay policy is why `primeAudio` exists: a context built before the page
 * has been touched starts suspended. Any first click — a name, readying up —
 * lands long before the first turn, so unlocking there is enough.
 */

/** One note: a frequency, when it starts, and how long it rings. Seconds. */
interface Note {
  freq: number
  at: number
  duration: number
}

/** Peak gain per note. Quiet enough to sit under a voice call. */
const PEAK = 0.16

/**
 * A rising fifth — two notes, the second overlapping the tail of the first. Up
 * rather than down, so it reads as "you're up" and not as a rejection;
 * overlapping, so it's one sound rather than two beeps of an alarm.
 */
const NOTES: Note[] = [
  { freq: 660, at: 0, duration: 0.18 },
  { freq: 990, at: 0.1, duration: 0.26 },
]

let ctx: AudioContext | null = null

/** Build and unlock the audio context on the first user gesture, once. */
export function primeAudio(): void {
  if (ctx) return
  const unlock = (): void => {
    if (ctx) return
    ctx = new AudioContext()
    void ctx.resume()
  }
  const opts = { once: true, passive: true } as const
  window.addEventListener('pointerdown', unlock, opts)
  window.addEventListener('keydown', unlock, opts)
}

/** Play the chime. A no-op until a gesture has unlocked the context. */
export function playChime(): void {
  if (!ctx) return
  // Backgrounding a tab can suspend the context; asking again is cheap and is
  // what makes the alert land in the case it exists for.
  void ctx.resume()
  const start = ctx.currentTime
  for (const note of NOTES) {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = note.freq
    // Ramp down to a floor rather than to zero: exponential ramps can't reach
    // it, and a hard stop at full gain clicks.
    gain.gain.setValueAtTime(PEAK, start + note.at)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + note.at + note.duration)
    osc.connect(gain).connect(ctx.destination)
    osc.start(start + note.at)
    osc.stop(start + note.at + note.duration)
  }
}
