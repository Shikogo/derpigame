<script setup lang="ts">
/**
 * A floating way back to the rules, pinned beside the theme switch. Opens itself
 * on a browser's first visit — a player who arrives on an invite link has no
 * other point where the game explains itself.
 */
import { onMounted, ref } from 'vue'

import HowToPlay from '@/components/HowToPlay.vue'
import IconHelp from '@/components/icons/IconHelp.vue'
import { usePreferencesStore } from '@/stores/preferences'

const prefs = usePreferencesStore()
const rules = ref<HTMLDialogElement | null>(null)

// Marked seen on the way in rather than on any particular way out, so Escape and
// the backdrop count the same as the button.
function open(): void {
  prefs.markRulesSeen()
  rules.value?.showModal()
}

// Native <dialog> doesn't dismiss on backdrop click; a click on the element
// itself (not its content) is the backdrop.
function onBackdrop(event: MouseEvent): void {
  if (event.target === rules.value) rules.value?.close()
}

onMounted(() => {
  if (!prefs.seenRules) open()
})
</script>

<template>
  <!-- `data-help-toggle` is the hook style.css uses to take this out of the way
       of a bottom-docked layout, the same as the theme switch beside it. -->
  <button
    type="button"
    data-help-toggle
    class="fixed bottom-4 right-16 z-50 flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface/80 text-ink-muted shadow-lg backdrop-blur transition-colors hover:border-turn hover:text-ink"
    aria-label="How to play"
    title="How to play"
    @click="open"
  >
    <IconHelp class="h-[1.15rem] w-[1.15rem]" />
  </button>

  <dialog
    ref="rules"
    class="m-auto w-[min(32rem,90vw)] bg-transparent p-0 backdrop:bg-black/60"
    @click="onBackdrop"
  >
    <HowToPlay @close="rules?.close()" />
  </dialog>
</template>
