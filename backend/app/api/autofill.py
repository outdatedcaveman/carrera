"""Autofill endpoints — Layer 3 of the form-autofill plan.

Three operations:

- ``POST /api/autofill/applications/{id}/start`` — kicks off a run. Spawns a
  worker thread that drives system Chrome via Playwright and fills the form.
  Returns immediately with a 202; client polls for status.
- ``GET /api/autofill/applications/{id}/status`` — polled by the UI ~1Hz
  while a run is in progress. Returns the run state + per-field reports.
- ``POST /api/autofill/applications/{id}/stop`` — tells the worker to
  release the browser so the user can finish submitting and we don't leave
  a Chrome instance hanging around.

Playwright import is local to the start endpoint so a missing install
returns a clean 503 instead of crashing the whole import chain on app
startup. The user can install playwright after launch with the
instructions surfaced in the UI.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, BaseResume, TailoredApplication, QuickAnswers as QAModel
from ..engine import autofill

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/autofill", tags=["autofill"])


@router.post("/applications/{application_id}/start", status_code=202)
def start_autofill(application_id: int, db: Session = Depends(get_db)):
    # Probe playwright import lazily — a fresh install of Carrera might not
    # have it yet (it bloats the bundle ~50MB and is opt-in for now).
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        raise HTTPException(
            503,
            "Playwright is not installed. Run `pip install playwright` in the "
            "backend's Python environment, then restart Carrera. Carrera will "
            "use your installed Chrome — no extra browser download needed.",
        )

    app_row = (
        db.query(TailoredApplication)
        .filter(TailoredApplication.id == application_id)
        .first()
    )
    if not app_row:
        raise HTTPException(404, "Tailored application not found")

    job = db.query(Job).filter(Job.id == app_row.job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.url:
        raise HTTPException(400, "Job has no URL to navigate to")

    # Build facts from Quick Answers + the tailored CV
    qa_row = db.query(QAModel).filter(QAModel.id == 1).first()
    qa_data = qa_row.data if qa_row else {}
    facts = autofill.build_facts(qa_data, app_row.tailored_resume_data or {})
    if not facts:
        raise HTTPException(
            422,
            "No data to fill from. Set up your Quick Answers in Settings and "
            "make sure your CV has at least name + email.",
        )

    existing = autofill.get_run(application_id)
    if existing and existing.status not in ("done", "error", "user_closed"):
        # Reuse the in-flight run so a double-click doesn't open two browsers
        return autofill.to_dict(existing)

    run = autofill.start_run(
        application_id=application_id,
        job_url=job.url,
        facts=facts,
        resume_pdf_path=app_row.resume_pdf_path,
    )
    return autofill.to_dict(run)


@router.get("/applications/{application_id}/status")
def autofill_status(application_id: int):
    run = autofill.get_run(application_id)
    if not run:
        raise HTTPException(404, "No autofill run for this application")
    return autofill.to_dict(run)


@router.post("/applications/{application_id}/stop")
def stop_autofill(application_id: int):
    ok = autofill.stop_run(application_id)
    if not ok:
        raise HTTPException(404, "No active run to stop")
    return {"ok": True}
