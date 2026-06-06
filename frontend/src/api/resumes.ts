import { api } from './client'
import type { BaseResume, ApplicationTemplate, CVData } from '../types'

export interface ResumeImportResult {
  resume: BaseResume
  source: 'pdf' | 'linkedin'
  parser: 'anthropic' | 'openai' | 'heuristic' | 'linkedin'
  summary: {
    full_name: boolean
    email: boolean
    phone: boolean
    summary: boolean
    experience_count: number
    education_count: number
    skills_count: number
    languages_count: number
    certifications_count: number
  }
}

async function importResume(args: {
  file: File
  name: string
  language: string
  isDefault?: boolean
}): Promise<ResumeImportResult> {
  const form = new FormData()
  form.append('file', args.file)
  form.append('name', args.name)
  form.append('language', args.language)
  form.append('is_default', String(args.isDefault ?? false))

  const res = await fetch('/api/resumes/import', { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export const resumesApi = {
  list: () => api.get<BaseResume[]>('/resumes'),
  get: (id: number) => api.get<BaseResume>(`/resumes/${id}`),
  create: (data: { name: string; language: string; is_default?: boolean; data: CVData }) =>
    api.post<BaseResume>('/resumes', data),
  update: (id: number, data: Partial<{ name: string; is_default: boolean; data: CVData }>) =>
    api.patch<BaseResume>(`/resumes/${id}`, data),
  delete: (id: number) => api.delete(`/resumes/${id}`),
  import: importResume,

  translate: (id: number, body: { target_language: 'en' | 'pt'; name?: string; is_default?: boolean }) =>
    api.post<BaseResume>(`/resumes/${id}/translate`, body),

  listTemplates: () => api.get<ApplicationTemplate[]>('/resumes/templates'),
  updateTemplate: (id: number, data: Partial<{ name: string; content: string; is_default: boolean }>) =>
    api.patch<ApplicationTemplate>(`/resumes/templates/${id}`, data),
}
