import { api } from './client'
import type { Source } from '../types'

export interface FetchAllResult {
  message: string
  source_ids: number[]
  results: Array<{
    id: number
    name: string
    ok: boolean
    added: number
    error: string | null
  }>
}

export const sourcesApi = {
  list: () => api.get<Source[]>('/sources'),
  get: (id: number) => api.get<Source>(`/sources/${id}`),
  create: (data: { name: string; type: string; config: Record<string, unknown>; enabled?: boolean }) =>
    api.post<Source>('/sources', data),
  update: (id: number, data: Partial<{ name: string; config: Record<string, unknown>; enabled: boolean }>) =>
    api.patch<Source>(`/sources/${id}`, data),
  delete: (id: number) => api.delete(`/sources/${id}`),
  triggerFetch: (id: number) => api.post(`/sources/${id}/fetch`),
  triggerFetchAll: () => api.post<FetchAllResult>('/sources/fetch-all'),
}
