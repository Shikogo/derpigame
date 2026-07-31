import { createRouter, createWebHashHistory } from 'vue-router'

import HomeView from '@/views/HomeView.vue'

// Hash history: GitHub Pages serves a single index.html, and #/room/<code>
// deep links resolve client-side without a 404 redirect trick.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      // The code is optional because streamer mode takes it out of the URL; the
      // tab carries it instead (`lib/roomCode.ts`).
      path: '/room/:code?',
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
      // The real room layout, driven by fabricated events — for the panel
      // cross-fade into the results screen and the confetti riding on it.
      path: '/sandbox/room',
      name: 'room-sandbox',
      component: () => import('@/views/sandbox/RoomSandbox.vue'),
    },
  ],
})
