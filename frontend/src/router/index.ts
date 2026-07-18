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
    {
      // Dev harness for exercising ImageViewer in isolation.
      path: '/sandbox/viewer',
      name: 'viewer-sandbox',
      component: () => import('@/views/ViewerSandbox.vue'),
    },
  ],
})
