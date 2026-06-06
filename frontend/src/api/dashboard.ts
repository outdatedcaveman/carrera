import { api } from './client'
import type { DashboardStats } from '../types'

export interface ActivityEntry {
  id: number
  job_id: number
  action: string
  details: string
  timestamp: string
  title: string
  company: string
}

export const dashboardApi = {
  stats: () => api.get<DashboardStats>('/dashboard/stats'),
  jobsOverTime: (days = 30) => api.get<{ date: string; count: number }[]>(`/dashboard/jobs-over-time?days=${days}`),
  categoryBreakdown: () => api.get<Record<string, number>>('/dashboard/category-breakdown'),
  statusBreakdown: () => api.get<Record<string, number>>('/dashboard/status-breakdown'),
  topCompanies: (limit = 10) => api.get<{ company: string; count: number }[]>(`/dashboard/top-companies?limit=${limit}`),
  recentActivity: (limit = 15) => api.get<ActivityEntry[]>(`/dashboard/recent-activity?limit=${limit}`),
  appliedThisWeek: () => api.get<{ date: string; count: number }[]>('/dashboard/applied-this-week'),
}
