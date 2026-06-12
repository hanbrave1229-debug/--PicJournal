<template>
  <el-config-provider :locale="zhCn">
    <el-container class="app-layout">
      <!-- ── Sidebar ─────────────────────────────────────────────── -->
      <el-aside width="220px" class="app-aside">
        <!-- Logo -->
        <div class="app-logo">
          <div class="app-logo-icon">
            <el-icon size="18"><Camera /></el-icon>
          </div>
          <span class="app-logo-name">Photo Manager</span>
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

          <el-menu-item index="/archive">
            <el-icon><Box /></el-icon>
            <span class="menu-item-text">归档箱</span>
            <span class="menu-iso-badge">隔离</span>
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
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

const route = useRoute()
const currentRoute = computed(() => route.path)
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
  background: rgba(52, 211, 153, 0.18);
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
</style>
