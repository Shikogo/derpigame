import { createRouter, createWebHashHistory } from 'vue-router'

import HomeView from '@/views/HomeView.vue'

// Hash history: GitHub Pages serves a single index.html, and #/room/<code>
// deep links resolve client-side without a 404 redirect trick.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/room/:code',
      name: 'room',
      component: () => import('@/views/RoomView.vue'),
      props: true,
    },
    // Dev harnesses (`src/views/sandbox/`): each exercises one piece without a
    // backend. Routed in every build — they're small, lazy, and unlinked.
    {
      path: '/sandbox/viewer',
      name: 'viewer-sandbox',
      component: () => import('@/views/sandbox/ViewerSandbox.vue'),
    },
    {
      path: '/sandbox/guess',
      name: 'guess-sandbox',
      component: () => import('@/views/sandbox/GuessSandbox.vue'),
    },
    {
      path: '/sandbox/confetti',
      name: 'confetti-sandbox',
      component: () => import('@/views/sandbox/ConfettiSandbox.vue'),
    },
    {
      // The real room layout, driven by fabricated events — for the panel
      // cross-fade into the results screen and the confetti riding on it.
      path: '/sandbox/room',
      name: 'room-sandbox',
      component: () => import('@/views/sandbox/RoomSandbox.vue'),
    },
  ],
})
