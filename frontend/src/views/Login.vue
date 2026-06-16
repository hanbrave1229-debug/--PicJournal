<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <el-icon size="22"><Camera /></el-icon>
      </div>
      <h1 class="login-title">拾光手账</h1>
      <p class="login-sub">
        {{ isSetup ? '首次使用，请创建管理员账号' : '请登录以访问你的照片库' }}
      </p>

      <el-form @submit.prevent="onSubmit" class="login-form">
        <el-input
          v-model="username"
          placeholder="用户名"
          size="large"
          :prefix-icon="User"
          autocomplete="username"
        />
        <el-input
          v-model="password"
          type="password"
          placeholder="密码"
          size="large"
          :prefix-icon="Lock"
          show-password
          autocomplete="current-password"
        />
        <el-input
          v-if="isSetup"
          v-model="confirmPassword"
          type="password"
          placeholder="确认密码"
          size="large"
          :prefix-icon="Lock"
          show-password
        />

        <el-button
          type="primary"
          size="large"
          native-type="submit"
          :loading="loading"
          class="login-submit"
        >
          {{ isSetup ? '创建并登录' : '登录' }}
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Camera, User, Lock } from '@element-plus/icons-vue'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/useAuthStore'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const isSetup = ref(false)
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)

onMounted(async () => {
  try {
    const { data } = await authApi.setupStatus()
    isSetup.value = !data.initialized
  } catch {
    /* if status check fails, default to login mode */
  }
})

async function onSubmit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (isSetup.value) {
    if (password.value.length < 6) {
      ElMessage.warning('密码至少 6 位')
      return
    }
    if (password.value !== confirmPassword.value) {
      ElMessage.warning('两次输入的密码不一致')
      return
    }
  }

  loading.value = true
  try {
    if (isSetup.value) {
      await auth.setup(username.value.trim(), password.value)
      ElMessage.success('管理员账号已创建')
    } else {
      await auth.login(username.value.trim(), password.value)
    }
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch {
    /* error toast handled by axios interceptor */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--no-bg-main, #0f1115);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--no-bg-card, #1a1d24);
  border: 1px solid var(--no-border-low, #2a2e38);
  border-radius: 16px;
  padding: 40px 32px;
  text-align: center;
}

.login-logo {
  width: 52px;
  height: 52px;
  margin: 0 auto 16px;
  border-radius: 14px;
  background: var(--no-accent, #34d399);
  color: var(--no-bg-main, #0f1115);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 20px rgba(52, 211, 153, 0.3);
}

.login-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 6px;
  color: var(--no-text-primary, #e5e7eb);
}

.login-sub {
  font-size: 13px;
  color: var(--no-text-muted, #9ca3af);
  margin: 0 0 28px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.login-submit {
  width: 100%;
  margin-top: 4px;
}
</style>
