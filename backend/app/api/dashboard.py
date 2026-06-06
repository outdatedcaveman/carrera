from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..database import get_db
from ..models import Job, Source, ActivityLog, TailoredApplication
from ..schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    new_today = db.query(Job).filter(Job.created_at >= today_start).count()
    total = db.query(Job).count()
    saved = db.query(Job).filter(Job.status == "saved").count()
    applied = db.query(Job).filter(Job.status == "applied").count()
    interviewing = db.query(Job).filter(Job.status == "interview").count()
    offers = db.query(Job).filter(Job.status == "offer").count()
    strong = db.query(Job).filter(Job.category == "strong_match").count()
    sources_active = db.query(Source).filter(Source.enabled == True).count()  # noqa: E712

    return DashboardStats(
        new_today=new_today,
        total_tracked=total,
        saved=saved,
        applied=applied,
        interviewing=interviewing,
        offers=offers,
        strong_matches=strong,
        sources_active=sources_active,
    )


@router.get("/jobs-over-time")
def jobs_over_time(days: int = 30, db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(Job.created_at).label("date"),
            func.count(Job.id).label("count"),
        )
        .filter(Job.created_at >= cutoff)
        .group_by(func.date(Job.created_at))
        .order_by(func.date(Job.created_at))
        .all()
    )
    return [{"date": str(r.date), "count": r.count} for r in rows]


@router.get("/category-breakdown")
def category_breakdown(db: Session = Depends(get_db)):
    rows = (
        db.query(Job.category, func.count(Job.id).label("count"))
        .group_by(Job.category)
        .all()
    )
    return {r.category: r.count for r in rows}


@router.get("/status-breakdown")
def status_breakdown(db: Session = Depends(get_db)):
    rows = (
        db.query(Job.status, func.count(Job.id).label("count"))
        .group_by(Job.status)
        .all()
    )
    return {r.status: r.count for r in rows}


@router.get("/top-companies")
def top_companies(limit: int = 10, db: Session = Depends(get_db)):
    rows = (
        db.query(Job.company, func.count(Job.id).label("count"))
        .group_by(Job.company)
        .order_by(func.count(Job.id).desc())
        .limit(limit)
        .all()
    )
    return [{"company": r.company, "count": r.count} for r in rows]


@router.get("/recent-activity")
def recent_activity(limit: int = Query(15, le=50), db: Session = Depends(get_db)):
    """Recent log of state changes — discovered, tailored, applied, status_change.

    Joins the activity_log to jobs so the UI can render "applied to {title} at
    {company}" without an extra round-trip. Skip log lines whose underlying job
    has been deleted (orphaned via CASCADE).
    """
    rows = (
        db.query(ActivityLog, Job)
        .join(Job, Job.id == ActivityLog.job_id)
        .order_by(desc(ActivityLog.timestamp))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "job_id": log.job_id,
            "action": log.action,
            "details": log.details,
            "timestamp": log.timestamp.isoformat(),
            "title": job.title,
            "company": job.company,
        }
        for log, job in rows
    ]


@router.get("/applied-this-week")
def applied_this_week(db: Session = Depends(get_db)):
    """Application velocity: applied counts per day for the trailing 7 days
    so the user can see whether they're keeping a steady pace."""
    today = datetime.utcnow().date()
    start = datetime.combine(today - timedelta(days=6), datetime.min.time())

    rows = (
        db.query(func.date(Job.applied_at).label("d"), func.count(Job.id).label("c"))
        .filter(Job.applied_at.isnot(None), Job.applied_at >= start)
        .group_by(func.date(Job.applied_at))
        .all()
    )
    by_day = {r.d: r.c for r in rows}
    out = []
    for i in range(7):
        d = today - timedelta(days=6 - i)
        out.append({"date": d.isoformat(), "count": by_day.get(d.isoformat(), 0)})
    return out
