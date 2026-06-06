import { api } from './client'
import type { Job, JobListResponse, JobStatus } from '../types'

export interface JobFilterOptions {
  sources: Array<{ id: number; name: string; type: string; count: number }>
  companies: Array<{ value: string; count: number }>
  seniority: Array<{ value: string; count: number }>
  categories: Array<{ value: string; count: number }>
}

export interface JobsListParams {
  status?: string
  category?: string
  source_id?: string             // comma-separated
  company?: string               // comma-separated, exact-match
  location?: string
  remote?: 'remote' | 'onsite' | ''
  seniority?: string             // comma-separated
  salary_min?: number
  salary_max?: number
  posted_within_days?: number
  search?: string
  sort_by?: string
  order?: string
  limit?: number
  offset?: number
}

export const jobsApi = {
  list: (params?: JobsListParams) => {
    const qs = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
      })
    }
    const query = qs.toString()
    return api.get<JobListResponse>(`/jobs${query ? `?${query}` : ''}`)
  },

  filterOptions: () => api.get<JobFilterOptions>('/jobs/filter-options'),

  get: (id: number) => api.get<Job>(`/jobs/${id}`),

  updateStatus: (id: number, status: JobStatus) =>
    api.patch<Job>(`/jobs/${id}`, { status }),

  updateNotes: (id: number, notes: string) =>
    api.patch<Job>(`/jobs/${id}`, { notes }),

  update: (id: number, data: Partial<Pick<Job, 'status' | 'notes' | 'applied_at'>>) =>
    api.patch<Job>(`/jobs/${id}`, data),

  delete: (id: number) => api.delete(`/jobs/${id}`),

  addNote: (id: number, note: string) =>
    api.post<Job>(`/jobs/${id}/note`, { note }),

  exportCsv: (status?: string) => {
    const qs = status ? `?status=${status}` : ''
    window.open(`/api/jobs/export/csv${qs}`, '_blank')
  },
}
