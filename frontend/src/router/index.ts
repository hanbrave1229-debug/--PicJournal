import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
    },
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
      path: '/archive',
      name: 'archive',
      component: () => import('@/views/Archive.vue'),
    },
    {
      path: '/smart-albums',
      name: 'smart-albums',
      component: () => import('@/views/SmartAlbums.vue'),
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
    {
      path: '/stacks/:stackId',
      name: 'stack-picker',
      component: () => import('@/views/StackPicker.vue'),
    },
    {
      path: '/places',
      name: 'places',
      component: () => import('@/views/Places.vue'),
    },
  ],
})

// Global guard: every route except /login requires a token. The token's real
// validity is enforced server-side; this just gates the UI and redirects.
router.beforeEach((to) => {
  const token = localStorage.getItem('picjournal_token')
  if (to.name === 'login') {
    // Already logged in? Skip the login page.
    return token ? { path: '/' } : true
  }
  if (!token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
