import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from ..database import get_db, SessionLocal
from ..models import Job, BaseResume, TailoredApplication, ActivityLog
from ..schemas import (
    TailoringRequest, TailoredApplicationOut,
    JobRequirementsAnalysis, CostEstimate,
)
from ..engine import tailoring_engine, pdf_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tailoring", tags=["tailoring"])

# How long to wait for reportlab to render a PDF before giving up.
# Generation is normally <2s; 30s is generous enough that legitimate work
# finishes but doesn't hang the user's UI for minutes when reportlab gets
# stuck on a font / encoding / Windows file-locking edge case.
PDF_GEN_TIMEOUT_S = 30


async def _generate_pdfs_async(app_id: int, resume_data: dict, cover_letter: str, job: Job) -> tuple[str | None, str | None]:
    """Run reportlab in a thread with a timeout. Returns (resume_path, cover_path).

    Either path can be None if generation failed or timed out — callers must
    handle that. We catch BaseException because reportlab has been observed
    raising things outside the normal Exception hierarchy on Windows.
    """
    def _do() -> tuple[str | None, str | None]:
        r = pdf_generator.generate_resume_pdf(resume_data, app_id)
        c = pdf_generator.generate_cover_letter_pdf(cover_letter, job, app_id)
        return (str(r) if r else None, str(c) if c else None)

    try:
        return await asyncio.wait_for(asyncio.to_thread(_do), timeout=PDF_GEN_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("PDF generation timed out for app_id=%d after %ds", app_id, PDF_GEN_TIMEOUT_S)
        return (None, None)
    except BaseException as e:
        logger.exception("PDF generation crashed for app_id=%d: %s", app_id, e)
        return (None, None)


@router.get("/analyze/{job_id}", response_model=JobRequirementsAnalysis)
def analyze_job(job_id: int, base_resume_id: int, db: Session = Depends(get_db)):
    """Extract requirements from job description and compare against base resume.

    GET (read-only) — the frontend calls this on every job-detail open. Was
    previously POST, which the frontend hit as GET → 404 ``Not Found`` on the
    Tailor & Apply view. Idempotent so GET is correct.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    resume = db.query(BaseResume).filter(BaseResume.id == base_resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")

    analysis = tailoring_engine.analyze_job_requirements(job.description, resume.data)
    return analysis


@router.post("/estimate-cost")
def estimate_cost(payload: TailoringRequest, db: Session = Depends(get_db)) -> CostEstimate:
    """Return estimated token cost before running AI tailoring."""
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    resume = db.query(BaseResume).filter(BaseResume.id == payload.base_resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")

    return tailoring_engine.estimate_cost(payload.ai_provider, payload.ai_model, job.description, resume.data)


@router.post("/generate", response_model=TailoredApplicationOut, status_code=201)
async def generate_tailored(payload: TailoringRequest, db: Session = Depends(get_db)):
    """Run the tailoring engine, store result, render PDFs (non-blocking)."""
    logger.info(
        "Tailoring start: job=%d resume=%d provider=%s lang=%s",
        payload.job_id, payload.base_resume_id, payload.ai_provider, payload.language,
    )
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    resume = db.query(BaseResume).filter(BaseResume.id == payload.base_resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")

    try:
        result = await tailoring_engine.generate_tailored_application(
            job=job,
            base_resume_data=resume.data,
            ai_provider=payload.ai_provider,
            ai_model=payload.ai_model,
            language=payload.language,
            emphasis=payload.emphasis,
            custom_instructions=payload.custom_instructions,
        )
    except tailoring_engine.TailoringError as e:
        logger.warning("Tailoring engine error: %s", e)
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.exception("Tailoring engine crashed")
        raise HTTPException(500, f"Tailoring failed: {e}") from e

    logger.info("Tailoring engine done; saving application")

    app = TailoredApplication(
        job_id=payload.job_id,
        base_resume_id=payload.base_resume_id,
        tailored_resume_data=result["resume_data"],
        cover_letter_text=result["cover_letter"],
        ai_model_used=result["model_used"],
        ai_cost_usd=result["cost_usd"],
        tailoring_notes=result["notes"],
    )
    db.add(app)
    db.add(ActivityLog(job_id=payload.job_id, action="tailored", details=f"Generated with {result['model_used']}"))
    db.commit()
    db.refresh(app)

    logger.info("Application saved id=%d; rendering PDFs (timeout %ds)", app.id, PDF_GEN_TIMEOUT_S)

    # Render PDFs in a worker thread with a timeout. If they hang or crash,
    # the request still returns within ~30s with the application data —
    # the user can re-render from the UI later.
    resume_path, cover_path = await _generate_pdfs_async(
        app.id, result["resume_data"], result["cover_letter"], job,
    )
    if resume_path or cover_path:
        app.resume_pdf_path = resume_path
        app.cover_letter_pdf_path = cover_path
        db.commit()
        db.refresh(app)
        logger.info("PDFs saved: resume=%s cover=%s", bool(resume_path), bool(cover_path))
    else:
        logger.warning("Both PDFs failed for app_id=%d; returning application without them", app.id)

    return app


@router.post("/bulk")
async def bulk_tailor(
    payload: dict,
    db: Session = Depends(get_db),
):
    """Tailor a batch of jobs sequentially.

    Body: ``{"job_ids": [...], "base_resume_id": int, "ai_provider": str,
    "language": "en"|"pt"}``.

    Returns one result per job: ``{"job_id", "ok", "application_id", "error"}``.
    Failures don't abort the batch — the caller gets per-job status so the UI
    can show what worked and what didn't. Skips jobs that already have a
    tailored application for the same base resume; the user clearly meant to
    fan out across new jobs, not redo old ones.
    """
    job_ids = payload.get("job_ids") or []
    base_resume_id = payload.get("base_resume_id")
    ai_provider = payload.get("ai_provider", "template")
    language = payload.get("language", "en")
    custom_instructions = payload.get("custom_instructions", "")

    if not job_ids:
        raise HTTPException(400, "job_ids is required")
    if base_resume_id is None:
        raise HTTPException(400, "base_resume_id is required")

    resume = db.query(BaseResume).filter(BaseResume.id == base_resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")

    results = []
    for jid in job_ids:
        job = db.query(Job).filter(Job.id == jid).first()
        if not job:
            results.append({"job_id": jid, "ok": False, "application_id": None, "error": "job not found"})
            continue

        # Skip if already tailored with this base resume
        existing = (
            db.query(TailoredApplication)
            .filter(TailoredApplication.job_id == jid,
                    TailoredApplication.base_resume_id == base_resume_id)
            .first()
        )
        if existing:
            results.append({
                "job_id": jid, "ok": True, "application_id": existing.id,
                "error": None, "skipped": True,
            })
            continue

        try:
            result = await tailoring_engine.generate_tailored_application(
                job=job,
                base_resume_data=resume.data,
                ai_provider=ai_provider,
                ai_model=None,
                language=language,
                emphasis=[],
                custom_instructions=custom_instructions,
            )
            app = TailoredApplication(
                job_id=jid,
                base_resume_id=base_resume_id,
                tailored_resume_data=result["resume_data"],
                cover_letter_text=result["cover_letter"],
                ai_model_used=result["model_used"],
                ai_cost_usd=result["cost_usd"],
                tailoring_notes=result["notes"],
            )
            db.add(app)
            db.add(ActivityLog(job_id=jid, action="tailored", details=f"Bulk: {result['model_used']}"))
            db.commit()
            db.refresh(app)

            # PDFs in the background — don't block subsequent jobs
            resume_path, cover_path = await _generate_pdfs_async(
                app.id, result["resume_data"], result["cover_letter"], job,
            )
            if resume_path or cover_path:
                app.resume_pdf_path = resume_path
                app.cover_letter_pdf_path = cover_path
                db.commit()

            results.append({
                "job_id": jid, "ok": True, "application_id": app.id,
                "error": None, "skipped": False,
            })
        except tailoring_engine.TailoringError as e:
            logger.warning("Bulk tailor: job %d failed: %s", jid, e)
            results.append({"job_id": jid, "ok": False, "application_id": None, "error": str(e)})
            db.rollback()
        except Exception as e:
            logger.exception("Bulk tailor: job %d crashed", jid)
            results.append({"job_id": jid, "ok": False, "application_id": None, "error": str(e)})
            db.rollback()

    ok_count = sum(1 for r in results if r["ok"])
    return {
        "message": f"Tailored {ok_count}/{len(results)} job(s)",
        "results": results,
    }


@router.post("/applications/{application_id}/regenerate-pdfs", response_model=TailoredApplicationOut)
async def regenerate_pdfs(application_id: int, db: Session = Depends(get_db)):
    """Re-render PDFs for an existing application — useful when the original
    rendering hung or crashed and the user wants to retry without redoing the
    LLM step."""
    app = db.query(TailoredApplication).filter(TailoredApplication.id == application_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    job = db.query(Job).filter(Job.id == app.job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    resume_path, cover_path = await _generate_pdfs_async(
        app.id, app.tailored_resume_data, app.cover_letter_text, job,
    )
    app.resume_pdf_path = resume_path
    app.cover_letter_pdf_path = cover_path
    db.commit()
    db.refresh(app)
    return app


@router.get("/applications/{job_id}", response_model=list[TailoredApplicationOut])
def list_applications(job_id: int, db: Session = Depends(get_db)):
    return (
        db.query(TailoredApplication)
        .filter(TailoredApplication.job_id == job_id)
        .order_by(TailoredApplication.created_at.desc())
        .all()
    )


@router.get("/applications/{application_id}/resume-pdf")
def download_resume_pdf(application_id: int, db: Session = Depends(get_db)):
    app = db.query(TailoredApplication).filter(TailoredApplication.id == application_id).first()
    if not app or not app.resume_pdf_path:
        raise HTTPException(404, "PDF not found")
    path = Path(app.resume_pdf_path)
    if not path.exists():
        raise HTTPException(404, "PDF file missing")
    return FileResponse(path, media_type="application/pdf", filename=f"resume_job{app.job_id}.pdf")


@router.get("/applications/{application_id}/cover-letter-pdf")
def download_cover_letter_pdf(application_id: int, db: Session = Depends(get_db)):
    app = db.query(TailoredApplication).filter(TailoredApplication.id == application_id).first()
    if not app or not app.cover_letter_pdf_path:
        raise HTTPException(404, "PDF not found")
    path = Path(app.cover_letter_pdf_path)
    if not path.exists():
        raise HTTPException(404, "PDF file missing")
    return FileResponse(path, media_type="application/pdf", filename=f"cover_letter_job{app.job_id}.pdf")


@router.delete("/applications/{application_id}", status_code=204)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    app = db.query(TailoredApplication).filter(TailoredApplication.id == application_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    db.delete(app)
    db.commit()
