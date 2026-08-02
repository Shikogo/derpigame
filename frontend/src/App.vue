<script setup lang="ts">
import HelpButton from '@/components/HelpButton.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { useTurnAlertStore } from '@/stores/turnAlert'

// Instantiated for its side effects — it marks the tab title and chimes when a
// turn arrives, from here so it's watching before any room is joined.
useTurnAlertStore()
</script>

<template>
  <RouterView />
  <HelpButton />
  <ThemeToggle />
</template>
