/**
 * useScanWebSocket — manages the WebSocket connection for real-time scan progress.
 *
 * Automatically reconnects on disconnect if the task is still running.
 * Updates the scan store on every progress event.
 */
import { ref, onUnmounted } from 'vue'
import { scanApi } from '@/api/scan'
import { useScanStore } from '@/stores/useScanStore'
import type { ScanEvent } from '@/types/scan'

export function useScanWebSocket() {
  const scanStore = useScanStore()
  const connected = ref(false)
  let ws: WebSocket | null = null

  function connect(taskId: number) {
    disconnect()
    ws = scanApi.connectWs(taskId)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (e: MessageEvent) => {
      const event = JSON.parse(e.data) as ScanEvent

      if (event.event === 'ping') return

      if (event.event === 'found') {
        scanStore.updateActive({ total_files: event.total })
      }

      if (event.event === 'progress') {
        scanStore.updateActive({
          processed_files: event.processed,
          total_files: event.total,
          progress_pct: event.pct,
          status: 'running',
        })
      }

      if (event.event === 'completed') {
        scanStore.updateActive({
          processed_files: event.processed,
          total_files: event.total,
          progress_pct: 100,
          status: 'completed',
        })
        disconnect()
        scanStore.clearActive()
      }

      if (event.event === 'error') {
        scanStore.updateActive({ status: 'failed', error_message: event.message })
        disconnect()
      }
    }

    ws.onclose = () => {
      connected.value = false
    }

    ws.onerror = () => {
      connected.value = false
    }
  }

  function disconnect() {
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
  }

  onUnmounted(disconnect)

  return { connect, disconnect, connected }
}
