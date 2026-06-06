from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


# ── Search Profile ─────────────────────────────────────────────────────────────

class SearchProfileConfig(BaseModel):
    titles: list[str] = []
    locations: list[str] = []
    salary_min_brl: float | None = None
    salary_max_brl: float | None = None
    salary_min_usd: float | None = None
    salary_max_usd: float | None = None
    remote_preference: str = "any"  # remote|hybrid|onsite|any
    required_keywords: list[str] = []
    preferred_keywords: list[str] = []
    excluded_keywords: list[str] = []
    excluded_companies: list[str] = []
    scoring_weights: dict[str, float] = {}


class SearchProfileCreate(BaseModel):
    name: str
    enabled: bool = True
    config: SearchProfileConfig = SearchProfileConfig()


class SearchProfileUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    config: SearchProfileConfig | None = None


class SearchProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    enabled: bool
    config: dict
    created_at: datetime
    updated_at: datetime


# ── Source ─────────────────────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    name: str
    type: str
    config: dict = {}
    enabled: bool = True


class SourceUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: str
    config: dict
    enabled: bool
    last_fetched: datetime | None
    last_error: str | None
    error_count: int
    jobs_found_total: int  # cumulative new rows ever inserted by this source's scrapes
    job_count: int = 0  # current job rows in DB for this source
    created_at: datetime


# ── Job ────────────────────────────────────────────────────────────────────────

class JobScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dimension: str
    weight: float
    raw_score: float
    weighted_score: float
    details: dict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    company: str
    location: str
    remote: bool | None
    url: str
    salary_min: float | None
    salary_max: float | None
    currency: str
    seniority: str | None
    employment_type: str | None
    score: float
    category: str
    status: str
    notes: str
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    posted_at: datetime | None
    source_id: int | None
    profile_id: int | None
    score_details: list[JobScoreOut] = []


class JobUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    applied_at: datetime | None = None


class JobListResponse(BaseModel):
    total: int
    items: list[JobOut]


# ── Dashboard ──────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    new_today: int
    total_tracked: int
    saved: int
    applied: int
    interviewing: int
    offers: int
    strong_matches: int
    sources_active: int


# ── Resume / CV ────────────────────────────────────────────────────────────────

class CVExperience(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str | None = None
    location: str = ""
    bullets: list[str] = []
    keywords: list[str] = []


class CVEducation(BaseModel):
    institution: str
    degree: str
    field: str
    start_date: str
    end_date: str | None = None
    notes: str = ""


class CVData(BaseModel):
    full_name: str
    email: str
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    website: str = ""
    summary: str = ""
    experience: list[CVExperience] = []
    education: list[CVEducation] = []
    skills: list[str] = []
    languages: list[dict[str, str]] = []  # [{"language": "Portuguese", "level": "Native"}]
    certifications: list[str] = []
    extra_sections: dict[str, Any] = {}


class BaseResumeCreate(BaseModel):
    name: str
    language: str = "en"
    is_default: bool = False
    data: CVData


class BaseResumeUpdate(BaseModel):
    name: str | None = None
    is_default: bool | None = None
    data: CVData | None = None


class BaseResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    language: str
    is_default: bool
    data: dict
    version: int
    created_at: datetime
    updated_at: datetime


# ── Tailoring ──────────────────────────────────────────────────────────────────

class TailoringRequest(BaseModel):
    job_id: int
    base_resume_id: int
    ai_provider: str = "template"  # template|ollama|openai|anthropic
    ai_model: str | None = None
    language: str = "en"  # en|pt
    emphasis: list[str] = []  # user-selected bullet IDs or keywords to emphasize
    custom_instructions: str = ""


class JobRequirementsAnalysis(BaseModel):
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: list[str]
    culture_keywords: list[str]
    seniority_level: str
    language_detected: str
    matching_experience: list[dict]
    skill_gaps: list[str]
    match_score: float


class TailoredApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    base_resume_id: int
    tailored_resume_data: dict
    cover_letter_text: str
    resume_pdf_path: str | None
    cover_letter_pdf_path: str | None
    ai_model_used: str
    ai_cost_usd: float
    tailoring_notes: dict
    created_at: datetime


class ApplicationTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: str
    language: str
    content: str
    is_default: bool
    created_at: datetime


class CostEstimate(BaseModel):
    provider: str
    model: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    free: bool


# ── Quick Answers (application form auto-fill) ────────────────────────────────

class QuickAnswersIdentity(BaseModel):
    full_name: str = ""
    preferred_name: str = ""
    pronouns: str = ""
    email: str = ""
    phone: str = ""
    current_city: str = ""
    current_country: str = ""
    linkedin: str = ""
    website: str = ""
    github: str = ""


class QuickAnswersWorkAuth(BaseModel):
    citizenship: str = ""  # ISO country code or free text
    visa_status: str = ""
    authorized_eu: str = "no"      # yes|no|unsure
    authorized_us: str = "no"
    authorized_uk: str = "no"
    authorized_br: str = "no"
    sponsorship_required: str = "no"


class QuickAnswersCompensation(BaseModel):
    target_min_salary: float | None = None
    target_max_salary: float | None = None
    preferred_currency: str = "BRL"
    open_to_equity: bool = True
    open_to_commission: bool = True


class QuickAnswersLogistics(BaseModel):
    notice_period_weeks: int = 4
    earliest_start_date: str = ""  # ISO date or empty
    willing_to_relocate: str = "depends"  # yes|no|depends
    willing_to_travel_pct: int = 25
    remote_preference: str = "any"  # remote|hybrid|onsite|any
    onsite_days_per_week: int = 0


class QuickAnswersBackground(BaseModel):
    highest_degree: str = ""
    university: str = ""
    graduation_year: str = ""
    total_years_experience: int = 0
    years_in_current_field: int = 0


class QuickAnswersEEO(BaseModel):
    """US-style voluntary self-identification. All optional; default to declined."""
    gender: str = "decline"
    race_ethnicity: str = "decline"
    veteran_status: str = "decline"
    disability_status: str = "decline"


class QuickAnswersBoilerplate(BaseModel):
    elevator_pitch: str = ""
    tell_me_about_yourself: str = ""
    why_looking: str = ""
    biggest_strength: str = ""
    biggest_weakness: str = ""


class QuickAnswersData(BaseModel):
    """The full schema. All sections optional; everything has defaults."""
    identity: QuickAnswersIdentity = QuickAnswersIdentity()
    work_auth: QuickAnswersWorkAuth = QuickAnswersWorkAuth()
    compensation: QuickAnswersCompensation = QuickAnswersCompensation()
    logistics: QuickAnswersLogistics = QuickAnswersLogistics()
    background: QuickAnswersBackground = QuickAnswersBackground()
    eeo: QuickAnswersEEO = QuickAnswersEEO()
    boilerplate: QuickAnswersBoilerplate = QuickAnswersBoilerplate()


class QuickAnswersOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    schema_version: int
    data: QuickAnswersData
    updated_at: datetime
