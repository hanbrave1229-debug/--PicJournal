import axios from 'axios'
import type {
  AIConfigResponse,
  AIConfigUpdate,
  ConnectionTestRequest,
  ConnectionTestResponse,
} from '@/types/config'

const BASE = '/api/v1/config'

export const configApi = {
  /** Get current AI config (api_key masked) */
  get(): Promise<{ data: AIConfigResponse }> {
    return axios.get(BASE)
  },

  /** Partial update — only pass ai_api_key when explicitly changed */
  update(body: AIConfigUpdate): Promise<{ data: AIConfigResponse }> {
    return axios.patch(BASE, body)
  },

  /**
   * Test connectivity with given credentials.
   * Does NOT save them — purely a probe call.
   */
  test(body: ConnectionTestRequest): Promise<{ data: ConnectionTestResponse }> {
    return axios.post(`${BASE}/test`, body)
  },
}
