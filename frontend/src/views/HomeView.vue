<script setup lang="ts">
/** Landing page: pick a name, then create a room or join one by code. */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { errorLabel } from '@/lib/errors'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const room = useRoomStore()
const session = useSessionStore()

const name = ref(session.name)
const joinCode = ref('')
const busy = ref(false)

async function create(): Promise<void> {
  if (!name.value.trim() || busy.value) return
  busy.value = true
  const ack = await room.createRoom(name.value.trim())
  busy.value = false
  if (ack.ok && room.code) router.push({ name: 'room', params: { code: room.code } })
}

async function join(): Promise<void> {
  const code = joinCode.value.trim().toLowerCase()
  if (!name.value.trim() || !code || busy.value) return
  busy.value = true
  const ack = await room.joinRoom(code, name.value.trim())
  busy.value = false
  if (ack.ok) router.push({ name: 'room', params: { code } })
}
</script>

<template>
  <main class="mx-auto flex min-h-full max-w-sm flex-col justify-center gap-6 p-8">
    <header class="text-center">
      <h1 class="text-4xl font-bold tracking-tight text-turn">Derpigame</h1>
      <p class="mt-1 text-sm text-gray-500">Guess the tags. Beat your friends.</p>
    </header>

    <label class="flex flex-col gap-1 text-sm">
      <span class="font-medium text-gray-600">Your name</span>
      <input
        v-model="name"
        type="text"
        placeholder="e.g. Twilight"
        class="rounded-lg border border-gray-300 px-3 py-2 focus:border-turn focus:outline-none"
        @keyup.enter="create"
      />
    </label>

    <button
      class="rounded-lg bg-turn px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
      :disabled="!name.trim() || busy"
      @click="create"
    >
      Create a room
    </button>

    <div class="flex items-center gap-3 text-xs text-gray-400">
      <span class="h-px flex-1 bg-gray-200" />or join one<span class="h-px flex-1 bg-gray-200" />
    </div>

    <form class="flex gap-2" @submit.prevent="join">
      <input
        v-model="joinCode"
        type="text"
        placeholder="Room code"
        class="w-full flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm uppercase focus:border-turn focus:outline-none"
      />
      <button
        type="submit"
        class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold hover:bg-gray-50 disabled:opacity-40"
        :disabled="!name.trim() || !joinCode.trim() || busy"
      >
        Join
      </button>
    </form>

    <p v-if="room.error" class="text-center text-sm text-wrong">{{ errorLabel(room.error) }}</p>
  </main>
</template>
