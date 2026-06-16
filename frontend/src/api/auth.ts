import api from './index'

export interface UserInfo {
  id: number
  username: string
  role: string
}

export interface LoginResponse {
  token: string
  user: UserInfo
}

export const authApi = {
  setupStatus() {
    return api.get<{ initialized: boolean }>('/auth/setup-status')
  },
  setup(username: string, password: string) {
    return api.post<LoginResponse>('/auth/setup', { username, password })
  },
  login(username: string, password: string) {
    return api.post<LoginResponse>('/auth/login', { username, password })
  },
  logout() {
    return api.post('/auth/logout')
  },
  me() {
    return api.get<UserInfo>('/auth/me')
  },
  changePassword(oldPassword: string, newPassword: string) {
    return api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  },
}
