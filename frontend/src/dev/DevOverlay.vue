<script setup lang="ts">
/**
 * Dev-only readouts and stand-ins for things the browser won't do on a desktop,
 * laid over the real room. Mounted by `RoomView` under `import.meta.env.DEV`, so
 * it's absent from a production build rather than merely hidden.
 *
 * Game states aren't faked here — the offline backend (`./run-local.sh --offline`)
 * serves images whose tags are known, so a round is played into whatever state
 * is worth looking at. What's left is the environment: an on-screen keyboard,
 * and whether the layout is keeping up.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useFrameRate } from '@/dev/useFrameRate'
import { useKeyboardInset } from '@/composables/useKeyboardInset'

const { fps, worst, janky, watch: sampleFrames, reset: resetFrames } = useFrameRate()

function sample(): void {
  resetFrames()
  sampleFrames()
}

/**
 * A stand-in keyboard: shrink the visual viewport the way Safari does and fire
 * the event it fires. A desktop window merely narrowed never does that, so
 * without this the whole iOS path — the measurement, the shell shrinking, the
 * sheet riding up, the viewer re-fitting — is unreachable outside a real phone.
 *
 * Overriding the height rather than writing `--kbd-inset` directly, so what runs
 * is the real measurement and not a stub of it.
 */
const FAKE_KEYBOARD_PX = 320
const fakeKeyboard = ref(false)

function toggleKeyboard(): void {
  const viewport = window.visualViewport
  if (!viewport) return
  fakeKeyboard.value = !fakeKeyboard.value
  if (fakeKeyboard.value) {
    Object.defineProperty(viewport, 'height', {
      configurable: true,
      get: () => window.innerHeight - FAKE_KEYBOARD_PX,
    })
  } else {
    // Deleting the own property hands `height` back to the prototype's getter.
    delete (viewport as unknown as Record<string, unknown>).height
  }
  viewport.dispatchEvent(new Event('resize'))
}

onBeforeUnmount(() => {
  if (fakeKeyboard.value) toggleKeyboard()
})

// What the layout is actually running on — the one readout worth having when
// the phone in your hand disagrees with the emulator.
const { inset } = useKeyboardInset()
const viewport = ref('')
function measure(): void {
  const vv = window.visualViewport
  viewport.value = `${window.innerWidth}×${window.innerHeight} · vv ${Math.round(vv?.height ?? 0)}`
}
onMounted(() => {
  measure()
  window.addEventListener('resize', measure)
  window.visualViewport?.addEventListener('resize', measure)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', measure)
  window.visualViewport?.removeEventListener('resize', measure)
})

// The bar sits where the mobile dock does, so it starts out of the way there.
// Remembered, because judging a layout means reloading it a lot and answering
// the same question each time is what makes a harness annoying.
const COLLAPSED_KEY = 'derpigame.dev.collapsed'
const collapsed = ref(localStorage.getItem(COLLAPSED_KEY) === 'true' || window.innerWidth < 1024)
watch(collapsed, (value) => localStorage.setItem(COLLAPSED_KEY, String(value)))
</script>

<template>
  <!-- Fixed, so the overlay never changes the layout it exists to measure. Above
       the confetti canvas (z-40) so the buttons stay clickable under a volley.

       Opaque, not blurred: sitting above the canvas puts the confetti in this
       bar's backdrop, and a full-width backdrop-filter re-blurs on every frame
       the paper moves. That's the harness making itself look slow.

       Below `lg` the bottom edge belongs to the guess dock, so the bar moves to
       the corner rather than sitting on the thing it exists to test. Collapsed,
       it goes to the corner everywhere: a full-width strip of chrome is exactly
       what's in the way when the layout is the thing being judged. -->
  <div
    class="fixed z-50 flex flex-wrap items-center justify-center gap-2 border-border bg-surface px-3 py-2 max-lg:right-2 max-lg:top-2 max-lg:max-w-[14rem] max-lg:flex-col max-lg:items-stretch max-lg:rounded-lg max-lg:border"
    :class="
      collapsed
        ? 'lg:bottom-2 lg:left-2 lg:rounded-lg lg:border'
        : 'lg:inset-x-0 lg:bottom-0 lg:border-t'
    "
  >
    <template v-if="!collapsed">
      <span class="mr-1 font-mono text-xs uppercase tracking-wider text-ink-faint">dev</span>
      <span class="mr-1 font-mono text-xs text-ink-faint tabular-nums">
        {{ viewport }} · kbd {{ inset }}
      </span>
      <!-- Fixed width: the digits change several times a second, and letting the
           readout resize shoves every button in this bar sideways as it does. -->
      <span v-if="worst" class="mr-1 w-56 shrink-0 font-mono text-xs text-ink-faint tabular-nums">
        {{ fps }}fps · worst {{ worst }}ms · {{ janky }} janky
      </span>
      <button
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium hover:border-turn hover:text-turn"
        title="Sample frame times for the next few seconds"
        @click="sample"
      >
        Sample frames
      </button>
      <button
        class="rounded-lg border px-3 py-1.5 text-xs font-medium"
        :class="
          fakeKeyboard
            ? 'border-turn bg-turn/10 text-turn'
            : 'border-border bg-raised hover:border-turn hover:text-turn'
        "
        @click="toggleKeyboard"
      >
        ⌨ keyboard
      </button>
    </template>
    <button
      class="rounded-lg px-2 py-1.5 text-xs text-ink-faint hover:text-ink"
      :title="collapsed ? 'Show dev controls' : 'Hide dev controls'"
      @click="collapsed = !collapsed"
    >
      {{ collapsed ? '▲ dev' : '▼' }}
    </button>
  </div>
</template>
