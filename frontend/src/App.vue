<template>
  <el-config-provider :locale="zhCn">
    <!-- Auth pages (login / first-deploy setup) render without the app shell -->
    <router-view v-if="isAuthRoute" />

    <template v-else>
    <el-container class="app-layout">
      <!-- ── Sidebar (desktop only) ────────────────────────────── -->
      <el-aside width="220px" class="app-aside">
        <!-- Logo -->
        <div class="app-logo">
          <div class="app-logo-icon">
            <el-icon size="18"><Camera /></el-icon>
          </div>
          <span class="app-logo-name">拾光手账</span>
        </div>

        <!-- Nav -->
        <el-menu
          :default-active="currentRoute"
          router
          class="app-menu"
        >
          <el-menu-item index="/">
            <el-icon><DataAnalysis /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/gallery">
            <el-icon><PictureFilled /></el-icon>
            <span>照片库</span>
          </el-menu-item>
          <el-menu-item index="/backup">
            <el-icon><UploadFilled /></el-icon>
            <span class="menu-item-text">手机备份</span>
            <span class="menu-new-badge">New</span>
          </el-menu-item>
          <el-menu-item index="/people">
            <el-icon><UserFilled /></el-icon>
            <span>智能分类</span>
          </el-menu-item>
          <el-menu-item index="/albums">
            <el-icon><Collection /></el-icon>
            <span>我的相册</span>
          </el-menu-item>
          <el-menu-item index="/diary">
            <el-icon><Notebook /></el-icon>
            <span class="menu-item-text">照片日记</span>
            <span class="menu-new-badge">New</span>
          </el-menu-item>
          <el-menu-item index="/memories">
            <el-icon><Sunrise /></el-icon>
            <span class="menu-item-text">回忆</span>
            <span class="menu-new-badge">New</span>
          </el-menu-item>

          <el-menu-item index="/places">
            <el-icon><MapLocation /></el-icon>
            <span>地点</span>
          </el-menu-item>

          <el-menu-item index="/archive">
            <el-icon><Box /></el-icon>
            <span>归档箱</span>
          </el-menu-item>

          <el-menu-item index="/smart-albums">
            <el-icon><MagicStick /></el-icon>
            <span>智能相册</span>
          </el-menu-item>

          <!-- Divider -->
          <div class="app-menu-divider" />

          <el-menu-item index="/duplicates">
            <el-icon><CopyDocument /></el-icon>
            <span class="menu-item-text">相似重复</span>
            <span class="menu-red-dot" />
          </el-menu-item>

          <el-menu-item index="/trash">
            <el-icon><Delete /></el-icon>
            <span>回收站</span>
          </el-menu-item>

          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>设置</span>
          </el-menu-item>
        </el-menu>

        <!-- NAS Status Widget -->
        <div class="app-nas-status">
          <div class="app-nas-ping">
            <span class="app-nas-ping-ring" />
            <span class="app-nas-ping-dot" />
          </div>
          <div class="app-nas-info">
            <span class="app-nas-name">DH4800 NAS</span>
            <span class="app-nas-ip">192.168.1.10</span>
          </div>
        </div>
      </el-aside>

      <!-- ── Main ───────────────────────────────────────────────── -->
      <el-container>
        <el-main class="app-main">
          <div class="app-main-inner">
            <router-view />
          </div>
        </el-main>
      </el-container>
    </el-container>

    <!-- ── Mobile bottom tab bar ─────────────────────────────────── -->
    <nav class="app-mobile-nav">
      <router-link to="/gallery" class="app-mobile-tab" :class="{ active: currentRoute.startsWith('/gallery') }">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
        <span>照片库</span>
      </router-link>
      <router-link to="/backup" class="app-mobile-tab" :class="{ active: currentRoute.startsWith('/backup') }">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <path d="M12 16V4M12 4l-4 4M12 4l4 4"/><path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>
        </svg>
        <span>备份</span>
      </router-link>
      <router-link to="/places" class="app-mobile-tab" :class="{ active: currentRoute.startsWith('/places') }">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
          <circle cx="12" cy="9" r="2.5"/>
        </svg>
        <span>地点</span>
      </router-link>
      <router-link to="/people" class="app-mobile-tab" :class="{ active: currentRoute.startsWith('/people') }">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>
        </svg>
        <span>人物</span>
      </router-link>
      <router-link to="/albums" class="app-mobile-tab" :class="{ active: currentRoute.startsWith('/albums') }">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>
        </svg>
        <span>相册</span>
      </router-link>
      <router-link to="/settings" class="app-mobile-tab" :class="{ active: currentRoute.startsWith('/settings') }">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
        </svg>
        <span>设置</span>
      </router-link>
    </nav>
    </template>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

const route = useRoute()
const currentRoute = computed(() => route.path)
const isAuthRoute = computed(() => route.name === 'login')
</script>

<style lang="scss">
// ── Layout shell ──────────────────────────────────────────────────────────
.app-layout {
  height: 100vh;
  overflow: hidden;
  background-color: var(--no-bg-main);
}

// ── Sidebar ───────────────────────────────────────────────────────────────
.app-aside {
  background-color: var(--no-bg-card);
  border-right: 1px solid var(--no-border-low);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

// ── Logo ──────────────────────────────────────────────────────────────────
.app-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 24px;
  height: 80px;
  flex-shrink: 0;
}

.app-logo-icon {
  width: 34px; height: 34px;
  border-radius: 10px;
  background: var(--no-accent);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--no-bg-main);
  box-shadow: 0 0 15px rgba(52, 211, 153, 0.3);
}

.app-logo-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--no-text-primary);
}

// ── Menu ──────────────────────────────────────────────────────────────────
.app-menu {
  flex: 1;
  background-color: var(--no-bg-card) !important;
  border-right: none !important;
  padding: 8px 0;
  overflow-y: auto;
  margin-top: 8px;
}

.app-menu-divider {
  height: 1px;
  background: var(--no-border-low);
  margin: 8px 16px;
}

.menu-item-text { flex: 1; }

.menu-new-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--no-accent);
  font-weight: 500;
  flex-shrink: 0;
}

.menu-red-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #f87171;
  opacity: 0.8;
  flex-shrink: 0;
}

.menu-iso-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(96, 165, 250, 0.14);
  color: #60a5fa;
  font-weight: 500;
  flex-shrink: 0;
}

// ── NAS Status Widget ─────────────────────────────────────────────────────
.app-nas-status {
  margin: 0 12px 16px;
  padding: 12px 14px;
  border-radius: var(--no-radius-btn);
  background: var(--no-bg-main);
  border: 1px solid var(--no-border-low);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.app-nas-ping {
  position: relative;
  width: 10px; height: 10px;
  flex-shrink: 0;
}

.app-nas-ping-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--no-accent);
  opacity: 0.75;
  animation: nas-ping 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.app-nas-ping-dot {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--no-accent);
}

.app-nas-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.app-nas-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--no-text-primary);
  white-space: nowrap;
}

.app-nas-ip {
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: var(--no-font-mono);
}

@keyframes nas-ping {
  75%, 100% {
    transform: scale(2);
    opacity: 0;
  }
}

// ── Main content ──────────────────────────────────────────────────────────
.app-main {
  padding: 0;
  overflow-y: auto;
  background-color: var(--no-bg-main);
}

.app-main-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px;
  min-height: 100%;
}

// ── Mobile bottom tab bar (hidden on desktop) ─────────────────────────────
.app-mobile-nav { display: none; }

@media (max-width: 768px) {
  // Hide sidebar on mobile
  .app-aside { display: none !important; }

  // Main fills full width; leave room for bottom nav
  .app-main-inner {
    padding: 12px 12px 80px; // bottom padding clears the nav
  }

  // Bottom tab bar
  .app-mobile-nav {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 58px;
    background: var(--no-bg-card);
    border-top: 1px solid var(--no-border-low);
    z-index: 200;
    // Safe-area support for notched phones
    padding-bottom: env(safe-area-inset-bottom, 0px);

    .app-mobile-tab {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      color: var(--no-text-secondary);
      text-decoration: none;
      font-size: 10px;
      transition: color 0.15s;

      svg { transition: color 0.15s; }

      &.active, &:hover {
        color: var(--el-color-primary);
      }
    }
  }
}
</style>
