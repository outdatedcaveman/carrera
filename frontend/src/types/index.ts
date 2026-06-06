export type JobStatus = 'discovered' | 'saved' | 'applied' | 'interview' | 'offer' | 'rejected'
export type JobCategory = 'strong_match' | 'good_match' | 'worth_a_look' | 'reach'

export interface JobScore {
  dimension: string
  weight: number
  raw_score: number
  weighted_score: number
  details: Record<string, unknown>
}

export interface Job {
  id: number
  title: string
  company: string
  location: string
  remote: boolean | null
  url: string
  description: string
  salary_min: number | null
  salary_max: number | null
  currency: string
  seniority: string | null
  employment_type: string | null
  score: number
  category: JobCategory
  status: JobStatus
  notes: string
  applied_at: string | null
  created_at: string
  updated_at: string
  posted_at: string | null
  source_id: number | null
  profile_id: number | null
  score_details: JobScore[]
}

export interface JobListResponse {
  total: number
  items: Job[]
}

export interface Source {
  id: number
  name: string
  type: string
  config: Record<string, unknown>
  enabled: boolean
  last_fetched: string | null
  last_error: string | null
  error_count: number
  jobs_found_total: number
  /** Rows currently in DB for this source (live count). */
  job_count?: number
  created_at: string
}

export interface SearchProfile {
  id: number
  name: string
  enabled: boolean
  config: SearchProfileConfig
  created_at: string
  updated_at: string
}

export interface SearchProfileConfig {
  titles: string[]
  locations: string[]
  salary_min_brl: number | null
  salary_max_brl: number | null
  salary_min_usd: number | null
  salary_max_usd: number | null
  remote_preference: 'remote' | 'hybrid' | 'onsite' | 'any'
  required_keywords: string[]
  preferred_keywords: string[]
  excluded_keywords: string[]
  excluded_companies: string[]
  scoring_weights: Record<string, number>
}

export interface DashboardStats {
  new_today: number
  total_tracked: number
  saved: number
  applied: number
  interviewing: number
  offers: number
  strong_matches: number
  sources_active: number
}

// ── Resume Types ───────────────────────────────────────────────────────────────

export interface CVExperience {
  company: string
  title: string
  start_date: string
  end_date: string | null
  location: string
  bullets: string[]
  keywords: string[]
}

export interface CVEducation {
  institution: string
  degree: string
  field: string
  start_date: string
  end_date: string | null
  notes: string
}

export interface CVData {
  full_name: string
  email: string
  phone: string
  location: string
  linkedin: string
  website: string
  summary: string
  experience: CVExperience[]
  education: CVEducation[]
  skills: string[]
  languages: { language: string; level: string }[]
  certifications: string[]
  extra_sections: Record<string, unknown>
}

export interface BaseResume {
  id: number
  name: string
  language: string
  is_default: boolean
  data: CVData
  version: number
  created_at: string
  updated_at: string
}

export interface ApplicationTemplate {
  id: number
  name: string
  type: string
  language: string
  content: string
  is_default: boolean
  created_at: string
}

// ── Tailoring Types ────────────────────────────────────────────────────────────

export interface JobRequirementsAnalysis {
  required_skills: string[]
  preferred_skills: string[]
  responsibilities: string[]
  culture_keywords: string[]
  seniority_level: string
  language_detected: string
  matching_experience: {
    index: number
    company: string
    title: string
    matched_skills: string[]
    relevance_score: number
  }[]
  skill_gaps: string[]
  match_score: number
}

export interface TailoredApplication {
  id: number
  job_id: number
  base_resume_id: number
  tailored_resume_data: CVData
  cover_letter_text: string
  resume_pdf_path: string | null
  cover_letter_pdf_path: string | null
  ai_model_used: string
  ai_cost_usd: number
  tailoring_notes: Record<string, unknown>
  created_at: string
}

export interface CostEstimate {
  provider: string
  model: string
  estimated_input_tokens: number
  estimated_output_tokens: number
  estimated_cost_usd: number
  free: boolean
}

export interface TailoringRequest {
  job_id: number
  base_resume_id: number
  ai_provider: 'template' | 'ollama' | 'openai' | 'anthropic'
  ai_model?: string
  language: 'en' | 'pt'
  emphasis: string[]
  custom_instructions: string
}
