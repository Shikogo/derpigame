<script setup lang="ts">
/**
 * The active round: the pan/zoom image beside the turn controls, guess box,
 * feed, and scoreboard. Shows a "round in progress" placeholder for a late
 * joiner who has no game snapshot yet (see the deferred mid-game-join note).
 */
import { computed } from 'vue'

import GuessFeed from '@/components/GuessFeed.vue'
import GuessInput from '@/components/GuessInput.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import Scoreboard from '@/components/Scoreboard.vue'
import TagProgress from '@/components/TagProgress.vue'
import TurnIndicator from '@/components/TurnIndicator.vue'
import TurnTimer from '@/components/TurnTimer.vue'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

const game = useGameStore()
const room = useRoomStore()

const live = computed(() => game.state.status === 'active' && !!game.state.image)
</script>

<template>
  <section v-if="live" class="flex flex-col gap-4 lg:flex-row">
    <div class="min-h-[45vh] flex-1 lg:min-h-[70vh]">
      <ImageViewer :src="game.state.image!.full_url" alt="Guess the tags" />
    </div>
    <aside class="flex w-full flex-col gap-4 lg:w-80">
      <div class="flex items-center justify-between">
        <TurnIndicator />
        <TurnTimer />
      </div>
      <TagProgress />
      <GuessInput v-if="!game.isSpectating" />
      <p
        v-else
        class="rounded-lg bg-turn/5 px-3 py-2 text-center text-sm text-gray-500"
      >
        👁 You're spectating — you'll join the next round.
      </p>
      <GuessFeed />
      <Scoreboard />
      <button
        v-if="!game.isSpectating"
        class="self-start text-xs text-gray-400 underline hover:text-wrong"
        @click="room.stopGame()"
      >
        Stop round
      </button>
    </aside>
  </section>

  <section v-else class="flex min-h-[45vh] flex-col items-center justify-center gap-2 text-center">
    <p class="text-lg font-medium">A round is already in progress.</p>
    <p class="text-sm text-gray-500">You’ll join automatically when the next round starts.</p>
  </section>
</template>
