from datetime import datetime
from sqlalchemy import (
    Integer, String, Float, Boolean, Text, DateTime, JSON,
    ForeignKey, Index, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="profile")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # linkedin|indeed|gupy|rss|remoteok|weworkremotely
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    jobs_found_total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="source")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="BRL")
    seniority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("search_profiles.id"), nullable=True)

    score: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String(64), default="worth_a_look")  # strong_match|good_match|worth_a_look|reach
    status: Mapped[str] = mapped_column(String(64), default="discovered")  # discovered|saved|applied|interview|offer|rejected
    notes: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    source: Mapped["Source | None"] = relationship("Source", back_populates="jobs")
    profile: Mapped["SearchProfile | None"] = relationship("SearchProfile", back_populates="jobs")
    score_details: Mapped[list["JobScore"]] = relationship("JobScore", back_populates="job", cascade="all, delete-orphan")
    activity_log: Mapped[list["ActivityLog"]] = relationship("ActivityLog", back_populates="job", cascade="all, delete-orphan")
    tailored_applications: Mapped[list["TailoredApplication"]] = relationship("TailoredApplication", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_url_hash", "url_hash", unique=True),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_score", "score"),
        Index("ix_jobs_created_at", "created_at"),
    )


class JobScore(Base):
    __tablename__ = "job_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    dimension: Mapped[str] = mapped_column(String(128))  # title|location|salary|skills|seniority|remote
    weight: Mapped[float] = mapped_column(Float)
    raw_score: Mapped[float] = mapped_column(Float)
    weighted_score: Mapped[float] = mapped_column(Float)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    job: Mapped["Job"] = relationship("Job", back_populates="score_details")


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(128))  # discovered|status_change|note_added|applied|tailored
    details: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship("Job", back_populates="activity_log")


# ── Resume & Tailoring ─────────────────────────────────────────────────────────

class BaseResume(Base):
    __tablename__ = "base_resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "Default - English"
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")  # en|pt
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)  # structured CV JSON
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tailored_applications: Mapped[list["TailoredApplication"]] = relationship("TailoredApplication", back_populates="base_resume")

    # Use a *partial* unique index — only one row per language can have
    # is_default=True. The previous full UniqueConstraint(language, is_default)
    # was wrong: it also disallowed multiple rows where is_default=False, so
    # users couldn't keep more than one non-default CV per language. The DB-side
    # migration in ``database.init_db`` drops the old constraint at startup.
    __table_args__ = (
        Index(
            "uq_base_resume_default_per_language",
            "language",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )


class ApplicationTemplate(Base):
    __tablename__ = "application_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # cover_letter|resume
    language: Mapped[str] = mapped_column(String(8), default="en")
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Jinja2 template
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuickAnswers(Base):
    """Singleton row holding the user's recurring application-form answers.

    Schema-versioned JSON blob rather than a wide nullable column table —
    fields evolve fast (every ATS asks about a slightly different thing) and
    a flat dict is easier to extend without migrations. Stored as id=1 by
    convention; the API treats it as a single resource.

    See ``docs/AUTOFILL_ROADMAP.md`` for the design rationale and the layered
    plan this is the foundation of.
    """
    __tablename__ = "quick_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppSetting(Base):
    """Key-value store for runtime app settings (API keys, model overrides, …).

    Kept as a flat key/value table so settings can be added without migrations
    — values are JSON-encoded so we can store strings, ints, or small objects.
    Reads are wrapped by ``settings_store`` which transparently falls back to
    the env-var-backed Pydantic Settings when a key is unset in the DB.
    """
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TailoredApplication(Base):
    __tablename__ = "tailored_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    base_resume_id: Mapped[int] = mapped_column(ForeignKey("base_resumes.id"))

    tailored_resume_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # modified CV JSON
    cover_letter_text: Mapped[str] = mapped_column(Text, default="")
    resume_pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_letter_pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    ai_model_used: Mapped[str] = mapped_column(String(128), default="template")  # template|ollama:model|openai:model|anthropic:model
    ai_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tailoring_notes: Mapped[dict] = mapped_column(JSON, default=dict)  # what was emphasized/changed

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship("Job", back_populates="tailored_applications")
    base_resume: Mapped["BaseResume"] = relationship("BaseResume", back_populates="tailored_applications")
