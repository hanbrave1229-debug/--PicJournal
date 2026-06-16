import axios from 'axios'
import { ElMessage } from 'element-plus'

const TOKEN_KEY = 'picjournal_token'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
})

// Attach the JWT to every request (also sent as a cookie for <img>/<video>).
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    if (status === 401) {
      // Token missing/expired — clear and bounce to login (avoid loop on /auth).
      localStorage.removeItem(TOKEN_KEY)
      const path = window.location.pathname
      if (path !== '/login') {
        window.location.href = '/login'
      }
      return Promise.reject(err)
    }
    const msg = err.response?.data?.detail ?? err.message ?? '请求失败'
    ElMessage.error(String(msg))
    return Promise.reject(err)
  },
)

export default api
