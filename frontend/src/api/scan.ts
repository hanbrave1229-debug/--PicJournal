import api from './index'
import type { ScanTask } from '@/types/scan'

export const scanApi = {
  start(scan_path: string) {
    return api.post<ScanTask>('/scan/start', { scan_path })
  },

  status(task_id: number) {
    return api.get<ScanTask>(`/scan/status/${task_id}`)
  },

  list() {
    return api.get<ScanTask[]>('/scan/tasks')
  },

  /** Create a WebSocket connection for real-time progress events */
  connectWs(task_id: number): WebSocket {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const token = localStorage.getItem('picjournal_token') ?? ''
    const qs = token ? `?token=${encodeURIComponent(token)}` : ''
    return new WebSocket(`${proto}://${location.host}/api/v1/scan/ws/${task_id}${qs}`)
  },
}
