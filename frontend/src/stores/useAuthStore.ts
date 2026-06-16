import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi, type UserInfo } from '@/api/auth'

const TOKEN_KEY = 'picjournal_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserInfo | null>(null)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem(TOKEN_KEY, t)
  }

  function clear() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  async function login(username: string, password: string) {
    const { data } = await authApi.login(username, password)
    setToken(data.token)
    user.value = data.user
  }

  async function setup(username: string, password: string) {
    const { data } = await authApi.setup(username, password)
    setToken(data.token)
    user.value = data.user
  }

  async function fetchMe() {
    const { data } = await authApi.me()
    user.value = data
    return data
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      /* ignore network errors on logout */
    }
    clear()
  }

  const isLoggedIn = () => !!token.value

  return { token, user, setToken, clear, login, setup, fetchMe, logout, isLoggedIn }
})
