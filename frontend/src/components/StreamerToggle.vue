<script setup lang="ts">
/**
 * Hide/show the room code, sat next to the code it hides. The button is also
 * the reveal — there's no temporary peek, because turning the mode off is one
 * click away and the invite Copy button works masked.
 */
import { computed } from 'vue'

import IconEye from '@/components/icons/IconEye.vue'
import IconEyeOff from '@/components/icons/IconEyeOff.vue'
import { usePreferencesStore } from '@/stores/preferences'

const prefs = usePreferencesStore()
const label = computed(() => (prefs.streamerMode ? 'Show room code' : 'Hide room code'))
</script>

<template>
  <button
    type="button"
    class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-faint transition-colors hover:bg-raised hover:text-ink"
    :class="prefs.streamerMode && 'text-turn'"
    :title="label"
    :aria-label="label"
    :aria-pressed="prefs.streamerMode"
    @click="prefs.toggle()"
  >
    <IconEyeOff v-if="prefs.streamerMode" class="h-[1.15rem] w-[1.15rem]" />
    <IconEye v-else class="h-[1.15rem] w-[1.15rem]" />
  </button>
</template>
