import { api } from './client'
import type {
  JobRequirementsAnalysis, TailoredApplication,
  CostEstimate, TailoringRequest,
} from '../types'

export const tailoringApi = {
  analyze: (jobId: number, baseResumeId: number) =>
    api.get<JobRequirementsAnalysis>(`/tailoring/analyze/${jobId}?base_resume_id=${baseResumeId}`),

  estimateCost: (req: TailoringRequest) =>
    api.post<CostEstimate>('/tailoring/estimate-cost', req),

  generate: (req: TailoringRequest) =>
    api.post<TailoredApplication>('/tailoring/generate', req),

  bulk: (payload: {
    job_ids: number[]
    base_resume_id: number
    ai_provider: string
    language: 'en' | 'pt'
    custom_instructions?: string
  }) => api.post<{
    message: string
    results: Array<{
      job_id: number
      ok: boolean
      application_id: number | null
      error: string | null
      skipped?: boolean
    }>
  }>('/tailoring/bulk', payload),

  regeneratePdfs: (applicationId: number) =>
    api.post<TailoredApplication>(`/tailoring/applications/${applicationId}/regenerate-pdfs`),

  listApplications: (jobId: number) =>
    api.get<TailoredApplication[]>(`/tailoring/applications/${jobId}`),

  deleteApplication: (id: number) =>
    api.delete(`/tailoring/applications/${id}`),

  resumePdfUrl: (applicationId: number) =>
    `/api/tailoring/applications/${applicationId}/resume-pdf`,

  coverLetterPdfUrl: (applicationId: number) =>
    `/api/tailoring/applications/${applicationId}/cover-letter-pdf`,
}
