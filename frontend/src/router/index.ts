import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
    },
    {
      path: '/gallery',
      name: 'gallery',
      component: () => import('@/views/Gallery.vue'),
    },
    {
      path: '/duplicates',
      name: 'duplicates',
      component: () => import('@/views/Duplicates.vue'),
    },
    {
      path: '/people',
      name: 'people',
      component: () => import('@/views/People.vue'),
    },
    {
      path: '/people/:id',
      name: 'person-detail',
      component: () => import('@/views/PersonDetail.vue'),
    },
    {
      path: '/albums',
      name: 'albums',
      component: () => import('@/views/Albums.vue'),
    },
    {
      path: '/albums/:id',
      name: 'album-detail',
      component: () => import('@/views/AlbumDetail.vue'),
    },
    {
      path: '/diary',
      name: 'diary',
      component: () => import('@/views/Diary.vue'),
    },
    {
      path: '/trash',
      name: 'trash',
      component: () => import('@/views/Trash.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/Settings.vue'),
    },
  ],
})

export default router
