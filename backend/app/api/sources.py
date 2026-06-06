from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models import Job, Source
from ..schemas import SourceCreate, SourceUpdate, SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])


def _source_out_with_job_count(db: Session, source: Source) -> SourceOut:
    n = (
        db.query(func.count(Job.id))
        .filter(Job.source_id == source.id)
        .scalar()
    )
    return SourceOut.model_validate(source).model_copy(update={"job_count": int(n or 0)})


@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    sources = db.query(Source).order_by(Source.name).all()
    count_rows = (
        db.query(Job.source_id, func.count(Job.id))
        .filter(Job.source_id.isnot(None))
        .group_by(Job.source_id)
        .all()
    )
    count_map = {sid: int(n) for sid, n in count_rows}
    return [
        SourceOut.model_validate(s).model_copy(update={"job_count": count_map.get(s.id, 0)})
        for s in sources
    ]


@router.post("", response_model=SourceOut, status_code=201)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return _source_out_with_job_count(db, source)


@router.post("/fetch-all")
async def trigger_fetch_all():
    """Run every enabled source sequentially on the server (single request; avoids N round-trips).

    Returns a per-source breakdown so the UI can show the user exactly what each
    source produced (or why it failed). Without this, the UI used to just say
    "Finished" — and users assumed only the source whose row visibly updated had
    actually run.
    """
    from ..engine.scheduler import run_source_now

    db = SessionLocal()
    try:
        enabled = (
            db.query(Source)
            .filter(Source.enabled.is_(True))
            .order_by(Source.id)
            .all()
        )
        ids_and_names = [(s.id, s.name, s.jobs_found_total) for s in enabled]
    finally:
        db.close()

    results = []
    for sid, name, before in ids_and_names:
        await run_source_now(sid)
        # Re-read to find delta + status
        db = SessionLocal()
        try:
            s = db.query(Source).filter(Source.id == sid).first()
            if s is None:
                results.append({"id": sid, "name": name, "ok": False, "added": 0,
                                "error": "source disappeared"})
                continue
            added = (s.jobs_found_total or 0) - (before or 0)
            results.append({
                "id": sid,
                "name": name,
                "ok": s.last_error is None,
                "added": added,
                "error": s.last_error,
            })
        finally:
            db.close()

    ok_count = sum(1 for r in results if r["ok"])
    total_added = sum(r["added"] for r in results)
    return {
        "message": f"Fetched {ok_count}/{len(results)} source(s); added {total_added} new job(s)",
        "source_ids": [r["id"] for r in results],
        "results": results,
    }


@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(404, "Source not found")
    return _source_out_with_job_count(db, source)


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: int, payload: SourceUpdate, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(404, "Source not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return _source_out_with_job_count(db, source)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(404, "Source not found")
    db.delete(source)
    db.commit()


@router.post("/{source_id}/fetch")
async def trigger_fetch(source_id: int):
    """Run scraper for one source and wait until it finishes (writes use their own DB session).

    Previously this used BackgroundTasks while the request still held ``get_db``'s session
    open until after the response was sent, which overlapped SQLite writes from the
    background job and could leave fetches effectively stuck or failing with
    ``database is locked``.
    """
    from ..engine.scheduler import run_source_now

    db = SessionLocal()
    try:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise HTTPException(404, "Source not found")
        name = source.name
    finally:
        db.close()

    await run_source_now(source_id)
    return {"message": f"Fetch finished for source '{name}'", "source_id": source_id}
