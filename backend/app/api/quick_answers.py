"""Quick Answers — the user's recurring application-form answers.

Singleton resource: one row at id=1. GET creates it if absent, seeded from
the user's default CV where possible (name, email, phone, location,
LinkedIn, latest education degree). PATCH accepts a partial nested update.

See ``docs/AUTOFILL_ROADMAP.md`` — this is Layer 1 of the form-autofill
plan and feeds Layer 2 (per-job answer generator) and Layer 3 (browser
autofill via Playwright).
"""
from datetime import datetime
import logging
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import QuickAnswers, BaseResume
from ..schemas import QuickAnswersData, QuickAnswersOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quick-answers", tags=["quick-answers"])


def _derive_from_cv(db: Session) -> QuickAnswersData:
    """Seed a fresh Quick Answers row from the user's default CV, if any."""
    out = QuickAnswersData()

    cv_row = (
        db.query(BaseResume)
        .filter(BaseResume.is_default.is_(True))
        .order_by(BaseResume.language)
        .first()
    )
    if cv_row is None:
        cv_row = db.query(BaseResume).order_by(BaseResume.id).first()
    if cv_row is None:
        return out

    cv = cv_row.data or {}

    # Identity
    out.identity.full_name = (cv.get("full_name") or "").strip()
    out.identity.email = (cv.get("email") or "").strip()
    out.identity.phone = (cv.get("phone") or "").strip()
    out.identity.linkedin = (cv.get("linkedin") or "").strip()
    out.identity.website = (cv.get("website") or "").strip()
    loc = (cv.get("location") or "").strip()
    if loc:
        # split "São Paulo, Brazil" → city + country
        parts = [p.strip() for p in re.split(r"[,/]", loc) if p.strip()]
        out.identity.current_city = parts[0] if parts else ""
        if len(parts) >= 2:
            out.identity.current_country = parts[-1]

    # Background — pick the most-recent education entry
    edu_list = cv.get("education") or []
    if edu_list:
        # Sort by end_date desc (string compare works for "YYYY-MM" / "YYYY")
        sorted_edu = sorted(
            edu_list,
            key=lambda e: (e.get("end_date") or e.get("start_date") or ""),
            reverse=True,
        )
        latest = sorted_edu[0]
        out.background.highest_degree = (latest.get("degree") or "").strip()
        out.background.university = (latest.get("institution") or "").strip()
        # Pull year out of "YYYY-MM" or bare "YYYY"
        end = (latest.get("end_date") or "").strip()
        m = re.match(r"^(\d{4})", end)
        if m:
            out.background.graduation_year = m.group(1)

    # Total years experience: subtract earliest experience start year from current year
    exp_list = cv.get("experience") or []
    earliest_year: int | None = None
    for e in exp_list:
        s = (e.get("start_date") or "").strip()
        m = re.match(r"^(\d{4})", s)
        if m:
            y = int(m.group(1))
            if earliest_year is None or y < earliest_year:
                earliest_year = y
    if earliest_year is not None:
        out.background.total_years_experience = max(0, datetime.utcnow().year - earliest_year)

    # Country-of-residence heuristic for default work-auth flags
    country = out.identity.current_country.lower()
    if any(k in country for k in ("brazil", "brasil", "br")):
        out.work_auth.authorized_br = "yes"
        out.compensation.preferred_currency = "BRL"
    if any(k in country for k in ("portugal", "spain", "germany", "france", "netherlands", "italy", "ireland", "european")):
        out.work_auth.authorized_eu = "yes"
        out.compensation.preferred_currency = "EUR"
    if any(k in country for k in ("united states", "usa", "us")):
        out.work_auth.authorized_us = "yes"
        out.compensation.preferred_currency = "USD"

    # Boilerplate seeds from CV summary
    out.boilerplate.elevator_pitch = (cv.get("summary") or "").strip()

    return out


def _get_or_create(db: Session) -> QuickAnswers:
    row = db.query(QuickAnswers).filter(QuickAnswers.id == 1).first()
    if row is None:
        seed = _derive_from_cv(db)
        row = QuickAnswers(id=1, schema_version=1, data=seed.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge patch into base. Lists/scalars in patch overwrite."""
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@router.get("", response_model=QuickAnswersOut)
def get_quick_answers(db: Session = Depends(get_db)):
    row = _get_or_create(db)
    return QuickAnswersOut(
        schema_version=row.schema_version,
        data=QuickAnswersData(**(row.data or {})),
        updated_at=row.updated_at,
    )


@router.patch("", response_model=QuickAnswersOut)
def update_quick_answers(payload: dict, db: Session = Depends(get_db)):
    """Accept a partial nested dict and merge it into the stored data.

    Frontend sends e.g. ``{"identity": {"phone": "+55…"}}`` and only that
    one field changes. Validate the merged result through the Pydantic
    model so unknown keys are dropped and types are coerced.
    """
    row = _get_or_create(db)
    merged = _deep_merge(row.data or {}, payload or {})
    # Round-trip through the schema to drop unknown keys / coerce types.
    validated = QuickAnswersData(**merged).model_dump()
    row.data = validated
    db.commit()
    db.refresh(row)
    return QuickAnswersOut(
        schema_version=row.schema_version,
        data=QuickAnswersData(**row.data),
        updated_at=row.updated_at,
    )


@router.post("/reseed", response_model=QuickAnswersOut)
def reseed_from_cv(db: Session = Depends(get_db)):
    """Re-derive defaults from the current CV (overwrites any blanks).

    Useful after the user imports a CV — we don't want them re-entering
    name/email/phone/LinkedIn that are already in the CV.
    """
    row = _get_or_create(db)
    fresh = _derive_from_cv(db).model_dump()
    existing = row.data or {}
    # Only overwrite empty fields in existing — the user's edits win.
    def merge_blanks(base: dict, defaults: dict) -> dict:
        out = dict(base)
        for k, v in defaults.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = merge_blanks(out[k], v)
            elif not out.get(k) and v not in ("", None, 0, False):
                out[k] = v
        return out
    merged = merge_blanks(existing, fresh)
    row.data = QuickAnswersData(**merged).model_dump()
    db.commit()
    db.refresh(row)
    return QuickAnswersOut(
        schema_version=row.schema_version,
        data=QuickAnswersData(**row.data),
        updated_at=row.updated_at,
    )
