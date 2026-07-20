<script setup lang="ts">
/** A floating light/dark switch, pinned to the corner and available everywhere. */
import { computed } from 'vue'

import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
const label = computed(() =>
  theme.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode',
)
</script>

<template>
  <button
    type="button"
    class="fixed bottom-4 right-4 z-50 flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface/80 text-ink-muted shadow-lg backdrop-blur transition-colors hover:border-turn hover:text-ink"
    :aria-label="label"
    :title="label"
    @click="theme.toggle()"
  >
    <!-- In dark mode, offer the sun (turn the lights on); in light, the moon. -->
    <svg
      v-if="theme.theme === 'dark'"
      class="h-[1.15rem] w-[1.15rem]"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path
        d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
      />
    </svg>
    <svg
      v-else
      class="h-[1.15rem] w-[1.15rem]"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  </button>
</template>
