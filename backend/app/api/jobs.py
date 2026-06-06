from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, desc, asc, func
from datetime import datetime, timedelta
import csv
import io
from ..database import get_db
from ..models import Job, ActivityLog, Source
from ..schemas import JobOut, JobUpdate, JobListResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    status: str | None = None,
    category: str | None = None,
    source_id: str | None = None,        # comma-separated for multi-select
    profile_id: int | None = None,
    search: str | None = None,
    company: str | None = None,          # comma-separated, exact match
    location: str | None = None,         # ILIKE substring
    remote: str | None = None,           # remote|onsite|any  (ternary)
    seniority: str | None = None,        # comma-separated
    salary_min: float | None = None,     # job's salary_max ≥ this OR no salary set
    salary_max: float | None = None,     # job's salary_min ≤ this OR no salary set
    posted_within_days: int | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Job).options(selectinload(Job.score_details))

    if status:
        q = q.filter(Job.status.in_(status.split(",")))
    if category:
        q = q.filter(Job.category == category)
    if source_id:
        ids = [int(x) for x in source_id.split(",") if x.strip().isdigit()]
        if ids:
            q = q.filter(Job.source_id.in_(ids))
    if profile_id:
        q = q.filter(Job.profile_id == profile_id)
    if search:
        term = f"%{search}%"
        q = q.filter(or_(
            Job.title.ilike(term),
            Job.company.ilike(term),
            Job.location.ilike(term),
            Job.description.ilike(term),
        ))
    if company:
        names = [c.strip() for c in company.split(",") if c.strip()]
        if names:
            q = q.filter(Job.company.in_(names))
    if location:
        q = q.filter(Job.location.ilike(f"%{location}%"))
    if remote == "remote":
        q = q.filter(Job.remote.is_(True))
    elif remote == "onsite":
        q = q.filter(or_(Job.remote.is_(False), Job.remote.is_(None)))
    if seniority:
        levels = [s.strip() for s in seniority.split(",") if s.strip()]
        if levels:
            q = q.filter(Job.seniority.in_(levels))
    if salary_min is not None:
        # Include jobs that meet the floor OR have no salary listed (so we
        # don't hide everything that didn't bother stating numbers).
        q = q.filter(or_(Job.salary_max >= salary_min, Job.salary_max.is_(None)))
    if salary_max is not None:
        q = q.filter(or_(Job.salary_min <= salary_max, Job.salary_min.is_(None)))
    if posted_within_days is not None and posted_within_days > 0:
        cutoff = datetime.utcnow() - timedelta(days=posted_within_days)
        # Posted_at is the source-reported date; fall back to discovery time.
        q = q.filter(or_(Job.posted_at >= cutoff, Job.created_at >= cutoff))

    total = q.count()

    sort_col = getattr(Job, sort_by, Job.created_at)
    q = q.order_by(desc(sort_col) if order == "desc" else asc(sort_col))
    items = q.offset(offset).limit(limit).all()

    return JobListResponse(total=total, items=items)


@router.get("/filter-options")
def filter_options(db: Session = Depends(get_db)):
    """Return distinct values for dropdown-style filters, with counts.

    Powers the Jobs page sidebar. We compute these on the fly because the
    set is small (~hundreds of distinct companies tops) and the user wants
    them sorted by frequency, not alphabet.
    """
    def _grouped(col, model=Job):
        rows = (
            db.query(col, func.count(model.id))
            .filter(col.isnot(None), col != "")
            .group_by(col)
            .order_by(func.count(model.id).desc())
            .all()
        )
        return [{"value": v, "count": c} for v, c in rows]

    sources = (
        db.query(Source.id, Source.name, Source.type, func.count(Job.id))
        .outerjoin(Job, Job.source_id == Source.id)
        .group_by(Source.id)
        .order_by(func.count(Job.id).desc())
        .all()
    )

    return {
        "sources": [
            {"id": sid, "name": name, "type": stype, "count": c}
            for sid, name, stype, c in sources
        ],
        "companies": _grouped(Job.company),
        "seniority": _grouped(Job.seniority),
        "categories": _grouped(Job.category),
    }


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).options(selectinload(Job.score_details)).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.patch("/{job_id}", response_model=JobOut)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    old_status = job.status
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(job, field, value)

    if payload.status and payload.status != old_status:
        db.add(ActivityLog(job_id=job_id, action="status_change", details=f"{old_status} → {payload.status}"))

    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    db.delete(job)
    db.commit()


@router.post("/{job_id}/note", response_model=JobOut)
def add_note(job_id: int, body: dict, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    note = body.get("note", "")
    job.notes = (job.notes + "\n\n" + note).strip()
    db.add(ActivityLog(job_id=job_id, action="note_added", details=note[:200]))
    db.commit()
    db.refresh(job)
    return job


@router.get("/export/csv")
def export_csv(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status.in_(status.split(",")))

    jobs = q.order_by(desc(Job.created_at)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "Company", "Location", "Remote", "URL", "Score", "Category", "Status", "Salary Min", "Salary Max", "Currency", "Applied At", "Created At"])
    for j in jobs:
        writer.writerow([j.id, j.title, j.company, j.location, j.remote, j.url, j.score, j.category, j.status, j.salary_min, j.salary_max, j.currency, j.applied_at, j.created_at])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=carrera_jobs_export.csv"},
    )
