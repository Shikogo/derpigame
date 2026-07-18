<script setup lang="ts">
/**
 * The turn controls that ride in the room's right rail during a live round:
 * whose turn + timer, tag progress, the guess box (or a spectator note), the
 * guess feed, and the scoreboard.
 */
import GuessFeed from '@/components/GuessFeed.vue'
import GuessInput from '@/components/GuessInput.vue'
import Scoreboard from '@/components/Scoreboard.vue'
import TagProgress from '@/components/TagProgress.vue'
import TurnIndicator from '@/components/TurnIndicator.vue'
import TurnTimer from '@/components/TurnTimer.vue'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

const game = useGameStore()
const room = useRoomStore()
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex items-center justify-between gap-3">
      <TurnIndicator />
      <TurnTimer />
    </div>
    <TagProgress />
    <GuessInput v-if="!game.isSpectating" />
    <p v-else class="rounded-lg bg-turn/5 px-3 py-2 text-center text-sm text-ink-muted">
      👁 You're spectating — you'll join the next round.
    </p>
    <GuessFeed />
    <Scoreboard />
    <button
      v-if="!game.isSpectating"
      class="self-start text-xs text-ink-faint underline hover:text-wrong"
      @click="room.stopGame()"
    >
      Stop round
    </button>
  </div>
</template>
