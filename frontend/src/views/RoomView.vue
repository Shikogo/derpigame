<script setup lang="ts">
defineProps<{ code: string }>()
</script>

<template>
  <main class="flex min-h-full flex-col items-center justify-center gap-4 p-8">
    <h1 class="text-2xl font-semibold">Room {{ code }}</h1>
    <RouterLink to="/" class="text-turn underline">Back</RouterLink>
  </main>
</template>
