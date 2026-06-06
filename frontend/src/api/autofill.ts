import { api } from './client'

export interface AutofillFieldReport {
  field_type: string | null
  label: string
  selector: string
  value_filled: string | null
  status: 'filled' | 'skipped_no_data' | 'skipped_unknown' | 'error'
  error: string | null
}

export interface AutofillRun {
  application_id: number
  job_url: string
  status: 'starting' | 'navigating' | 'filling' | 'done' | 'error' | 'user_closed'
  message: string
  fields_total: number
  fields_filled: number
  reports: AutofillFieldReport[]
  started_at: number
  elapsed_s: number
  error: string | null
}

export const autofillApi = {
  start: (appId: number) => api.post<AutofillRun>(`/autofill/applications/${appId}/start`),
  status: (appId: number) => api.get<AutofillRun>(`/autofill/applications/${appId}/status`),
  stop: (appId: number) => api.post(`/autofill/applications/${appId}/stop`),
}
