import { api } from './client'

export interface AISettings {
  anthropic_api_key_set: boolean
  anthropic_api_key_hint: string
  anthropic_model: string
  openai_api_key_set: boolean
  openai_api_key_hint: string
  openai_model: string
  ollama_base_url: string
  ollama_model: string
}

export interface AISettingsUpdate {
  anthropic_api_key?: string
  anthropic_model?: string
  openai_api_key?: string
  openai_model?: string
  ollama_base_url?: string
  ollama_model?: string
}

export const appSettingsApi = {
  getAi: () => api.get<AISettings>('/settings/ai'),
  updateAi: (patch: AISettingsUpdate) => api.patch<AISettings>('/settings/ai', patch),
}
