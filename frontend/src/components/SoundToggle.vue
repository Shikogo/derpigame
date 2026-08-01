<script setup lang="ts">
/**
 * Mute the turn chime. Sat in the room header beside the other local
 * preferences, because muting is something you reach for mid-game.
 */
import { computed } from 'vue'

import IconVolume from '@/components/icons/IconVolume.vue'
import IconVolumeOff from '@/components/icons/IconVolumeOff.vue'
import { usePreferencesStore } from '@/stores/preferences'

const prefs = usePreferencesStore()
const label = computed(() => (prefs.sound ? 'Mute turn sound' : 'Unmute turn sound'))
</script>

<template>
  <button
    type="button"
    class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-faint transition-colors hover:bg-raised hover:text-ink"
    :class="!prefs.sound && 'text-turn'"
    :title="label"
    :aria-label="label"
    :aria-pressed="!prefs.sound"
    @click="prefs.toggleSound()"
  >
    <IconVolume v-if="prefs.sound" class="h-[1.15rem] w-[1.15rem]" />
    <IconVolumeOff v-else class="h-[1.15rem] w-[1.15rem]" />
  </button>
</template>
