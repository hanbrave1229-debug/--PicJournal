/** Supported AI provider identifiers */
export type AIProvider = 'openai' | 'anthropic' | 'qianwen' | 'custom' | ''

export interface AIConfigResponse {
  ai_provider: AIProvider
  /** Masked key, e.g. "sk-...Ab1c" */
  ai_api_key_masked: string
  ai_model: string
  ai_base_url: string | null
  ai_enabled: boolean
  ai_auto_tag: boolean
  ai_batch_size: number
}

export interface AIConfigUpdate {
  ai_provider?: AIProvider
  /** Only pass when the user explicitly changes the key */
  ai_api_key?: string
  ai_model?: string
  ai_base_url?: string | null
  ai_enabled?: boolean
  ai_auto_tag?: boolean
  ai_batch_size?: number
}

export interface ConnectionTestRequest {
  provider: AIProvider
  api_key: string
  model: string
  base_url?: string | null
}

export interface ConnectionTestResponse {
  ok: boolean
  message: string
  latency_ms: number | null
}

// ── Static provider / model catalogue ────────────────────────────────────────

export interface ProviderMeta {
  id: AIProvider
  label: string
  /** Short domain label shown in the card */
  domain: string
  color: string
  models: { value: string; label: string }[]
  keyPlaceholder: string
  baseUrlRequired: boolean
}

export const PROVIDERS: ProviderMeta[] = [
  {
    id: 'openai',
    label: 'OpenAI',
    domain: 'api.openai.com',
    color: '#10a37f',
    models: [
      { value: 'gpt-4o',          label: 'GPT-4o' },
      { value: 'gpt-4o-mini',     label: 'GPT-4o mini（推荐）' },
      { value: 'gpt-4-turbo',     label: 'GPT-4 Turbo' },
    ],
    keyPlaceholder: 'sk-...',
    baseUrlRequired: false,
  },
  {
    id: 'anthropic',
    label: 'Anthropic Claude',
    domain: 'api.anthropic.com',
    color: '#d97706',
    models: [
      { value: 'claude-haiku-4-5-20251001',  label: 'Claude Haiku 4.5（最快）' },
      { value: 'claude-sonnet-4-6',          label: 'Claude Sonnet 4.6（推荐）' },
      { value: 'claude-opus-4-8',            label: 'Claude Opus 4.8（最强）' },
    ],
    keyPlaceholder: 'sk-ant-...',
    baseUrlRequired: false,
  },
  {
    id: 'qianwen',
    label: '阿里通义千问',
    domain: 'dashscope.aliyuncs.com',
    color: '#f97316',
    models: [
      { value: 'qwen-vl-plus',   label: 'Qwen-VL-Plus' },
      { value: 'qwen-vl-max',    label: 'Qwen-VL-Max（推荐）' },
      { value: 'qwen-turbo',     label: 'Qwen-Turbo' },
    ],
    keyPlaceholder: 'sk-...',
    baseUrlRequired: false,
  },
  {
    id: 'custom',
    label: '自定义（兼容 OpenAI）',
    domain: '自定义端点',
    color: '#8b5cf6',
    models: [],
    keyPlaceholder: 'sk-...',
    baseUrlRequired: true,
  },
]
