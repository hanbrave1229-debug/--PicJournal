export type ScanStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ScanTask {
  id: number
  scan_path: string
  status: ScanStatus
  total_files: number
  processed_files: number
  progress_pct: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

/** WebSocket progress event shapes */
export type ScanEvent =
  | { event: 'started'; task_id: number }
  | { event: 'walking'; path: string }
  | { event: 'found'; total: number }
  | { event: 'progress'; processed: number; total: number; pct: number }
  | { event: 'completed'; processed: number; total: number }
  | { event: 'error'; message: string }
  | { event: 'ping' }
