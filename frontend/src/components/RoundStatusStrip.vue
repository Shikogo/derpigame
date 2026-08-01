<script setup lang="ts">
/**
 * Whose turn it is, how long they have, and how far the room has got — the
 * three things you need in view while you think of a tag.
 *
 * In the rail it's a plain stack. On a phone it's the band between the picture
 * and the guess box, so it takes a surface of its own to sit on: unconditional
 * `max-lg:` classes, safe because this only renders during a live round, which
 * is exactly when the room runs its mobile shell.
 */
import { computed } from 'vue'

import TagProgress from '@/components/TagProgress.vue'
import TurnIndicator from '@/components/TurnIndicator.vue'
import TurnTimer from '@/components/TurnTimer.vue'
import { useGameStore } from '@/stores/game'
import { useTurnAlertStore } from '@/stores/turnAlert'

// A viewport with the keyboard open has room for the turn and the bar, and not
// much else. Drops the bonus chips rather than letting the picture pay for them.
withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const game = useGameStore()
const turnAlert = useTurnAlertStore()

// `isMyTurn` as well, so the flag outliving a fast handoff can't shout over
// somebody else's turn.
const banner = computed(() => turnAlert.justArrived && game.isMyTurn)
</script>

<template>
  <div
    class="flex flex-col gap-4 max-lg:gap-2 max-lg:border-t max-lg:border-border max-lg:bg-surface max-lg:px-3 max-lg:py-2"
  >
    <div class="flex items-center justify-between gap-3">
      <TurnIndicator :banner="banner" />
      <TurnTimer />
    </div>
    <TagProgress :compact="compact" />
  </div>
</template>
