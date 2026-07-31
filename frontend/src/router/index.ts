import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

import HomeView from '@/views/HomeView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: HomeView },
  {
    // The code is optional because streamer mode takes it out of the URL; the
    // tab carries it instead (`lib/roomCode.ts`).
    path: '/room/:code?',
    name: 'room',
    component: () => import('@/views/RoomView.vue'),
    props: true,
  },
]

// `import.meta.env.DEV` is a compile-time constant, so a production build drops
// this branch and never reaches the import — nothing under `src/dev/` ships.
if (import.meta.env.DEV) {
  routes.push({
    // The viewer, alone in a bounded frame with a transform readout: pan, zoom
    // and clamp are geometry, and a game around them only gets in the way.
    path: '/dev/viewer',
    name: 'dev-viewer',
    component: () => import('@/dev/ViewerHarness.vue'),
  })
}

// Hash history: GitHub Pages serves a single index.html, and #/room/<code>
// deep links resolve client-side without a 404 redirect trick.
export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})
