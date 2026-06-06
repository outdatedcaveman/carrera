import { api } from './client'

export interface QuickAnswersIdentity {
  full_name: string
  preferred_name: string
  pronouns: string
  email: string
  phone: string
  current_city: string
  current_country: string
  linkedin: string
  website: string
  github: string
}

export interface QuickAnswersWorkAuth {
  citizenship: string
  visa_status: string
  authorized_eu: string
  authorized_us: string
  authorized_uk: string
  authorized_br: string
  sponsorship_required: string
}

export interface QuickAnswersCompensation {
  target_min_salary: number | null
  target_max_salary: number | null
  preferred_currency: string
  open_to_equity: boolean
  open_to_commission: boolean
}

export interface QuickAnswersLogistics {
  notice_period_weeks: number
  earliest_start_date: string
  willing_to_relocate: string
  willing_to_travel_pct: number
  remote_preference: string
  onsite_days_per_week: number
}

export interface QuickAnswersBackground {
  highest_degree: string
  university: string
  graduation_year: string
  total_years_experience: number
  years_in_current_field: number
}

export interface QuickAnswersEEO {
  gender: string
  race_ethnicity: string
  veteran_status: string
  disability_status: string
}

export interface QuickAnswersBoilerplate {
  elevator_pitch: string
  tell_me_about_yourself: string
  why_looking: string
  biggest_strength: string
  biggest_weakness: string
}

export interface QuickAnswersData {
  identity: QuickAnswersIdentity
  work_auth: QuickAnswersWorkAuth
  compensation: QuickAnswersCompensation
  logistics: QuickAnswersLogistics
  background: QuickAnswersBackground
  eeo: QuickAnswersEEO
  boilerplate: QuickAnswersBoilerplate
}

export interface QuickAnswers {
  schema_version: number
  data: QuickAnswersData
  updated_at: string
}

export type QuickAnswersPatch = Partial<{
  identity: Partial<QuickAnswersIdentity>
  work_auth: Partial<QuickAnswersWorkAuth>
  compensation: Partial<QuickAnswersCompensation>
  logistics: Partial<QuickAnswersLogistics>
  background: Partial<QuickAnswersBackground>
  eeo: Partial<QuickAnswersEEO>
  boilerplate: Partial<QuickAnswersBoilerplate>
}>

export const quickAnswersApi = {
  get: () => api.get<QuickAnswers>('/quick-answers'),
  update: (patch: QuickAnswersPatch) => api.patch<QuickAnswers>('/quick-answers', patch),
  reseedFromCv: () => api.post<QuickAnswers>('/quick-answers/reseed'),
}
