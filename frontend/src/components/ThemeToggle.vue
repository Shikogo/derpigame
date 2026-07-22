<script setup lang="ts">
/** A floating light/dark switch, pinned to the corner and available everywhere. */
import { computed } from 'vue'

import IconMoon from '@/components/icons/IconMoon.vue'
import IconSun from '@/components/icons/IconSun.vue'
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
    <IconSun v-if="theme.theme === 'dark'" class="h-[1.15rem] w-[1.15rem]" />
    <IconMoon v-else class="h-[1.15rem] w-[1.15rem]" />
  </button>
</template>
