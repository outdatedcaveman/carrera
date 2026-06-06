import { api } from './client'
import type { SearchProfile, SearchProfileConfig } from '../types'

export const profilesApi = {
  list: () => api.get<SearchProfile[]>('/profiles'),
  get: (id: number) => api.get<SearchProfile>(`/profiles/${id}`),
  create: (data: { name: string; enabled?: boolean; config?: Partial<SearchProfileConfig> }) =>
    api.post<SearchProfile>('/profiles', data),
  update: (id: number, data: Partial<{ name: string; enabled: boolean; config: SearchProfileConfig }>) =>
    api.patch<SearchProfile>(`/profiles/${id}`, data),
  delete: (id: number) => api.delete(`/profiles/${id}`),
}
