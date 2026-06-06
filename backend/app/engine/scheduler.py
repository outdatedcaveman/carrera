"""APScheduler-based job run engine."""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Source, Job, JobScore, ActivityLog
from ..scrapers.base import get_scraper, RawJob
from ..engine.scorer import score_job
from ..engine.dedup import is_duplicate
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler()


def start_scheduler():
    parts = settings.scrape_schedule.split()
    if len(parts) == 5:
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]
        )
    else:
        trigger = CronTrigger(hour="8,18")

    scheduler.add_job(run_all_sources, trigger, id="scrape_all", replace_existing=True)
    scheduler.start()
    logger.info(f"Scheduler started. Schedule: {settings.scrape_schedule}")


def stop_scheduler():
    scheduler.shutdown(wait=False)


async def run_all_sources():
    db = SessionLocal()
    try:
        sources = db.query(Source).filter(Source.enabled == True).all()  # noqa: E712
        logger.info(f"Running {len(sources)} sources")
        for source in sources:
            await _run_source(db, source)
    finally:
        db.close()


async def run_source_now(source_id: int):
    db = SessionLocal()
    try:
        source = db.query(Source).filter(Source.id == source_id).first()
        if source:
            await _run_source(db, source)
    finally:
        db.close()


async def _run_source(db: Session, source: Source):
    logger.info(f"Fetching source: {source.name} (type={source.type})")
    try:
        scraper = get_scraper(source.type, source.config)
        raw_jobs = await scraper.fetch()
    except Exception as e:
        logger.error(f"Scraper error for '{source.name}': {e}")
        source.last_error = str(e)
        source.error_count += 1
        source.last_fetched = datetime.utcnow()
        db.commit()
        return

    # Load active profiles for scoring
    from ..models import SearchProfile
    profiles = db.query(SearchProfile).filter(SearchProfile.enabled == True).all()  # noqa: E712
    default_profile = profiles[0] if profiles else None

    new_count = 0
    for raw in raw_jobs:
        if is_duplicate(db, raw):
            continue

        best_score = 0.0
        best_category = "worth_a_look"
        best_score_details = []
        best_profile_id = None

        for profile in profiles:
            s, cat, details = score_job(raw, profile)
            if s > best_score:
                best_score = s
                best_category = cat
                best_score_details = details
                best_profile_id = profile.id

        job = Job(
            title=raw.title,
            company=raw.company,
            location=raw.location,
            url=raw.url,
            url_hash=raw.url_hash,
            description=raw.description,
            salary_min=raw.salary_min,
            salary_max=raw.salary_max,
            currency=raw.currency,
            remote=raw.remote,
            seniority=raw.seniority,
            employment_type=raw.employment_type,
            posted_at=raw.posted_at,
            source_id=source.id,
            profile_id=best_profile_id,
            score=best_score,
            category=best_category,
            status="discovered",
        )
        db.add(job)
        db.flush()

        for sd in best_score_details:
            sd.job_id = job.id
            db.add(sd)

        db.add(ActivityLog(job_id=job.id, action="discovered", details=f"via {source.name}"))
        new_count += 1

    source.last_fetched = datetime.utcnow()
    source.last_error = None
    source.jobs_found_total += new_count
    db.commit()

    logger.info(f"Source '{source.name}': added {new_count} new jobs")
