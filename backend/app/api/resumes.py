import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import BaseResume, ApplicationTemplate
from ..schemas import (
    BaseResumeCreate, BaseResumeUpdate, BaseResumeOut,
    ApplicationTemplateOut, CVData,
)
from ..engine.cv_importer import (
    CVImportError,
    extract_pdf_text,
    parse_cv_text_with_llm,
    parse_linkedin_archive,
    summarize_extracted,
    translate_cv,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])

# Upload safety cap (bytes). A typical CV PDF is <2 MB; LinkedIn exports <20 MB.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


# ── Base Resumes ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[BaseResumeOut])
def list_resumes(db: Session = Depends(get_db)):
    return db.query(BaseResume).order_by(BaseResume.language, BaseResume.name).all()


@router.post("", response_model=BaseResumeOut, status_code=201)
def create_resume(payload: BaseResumeCreate, db: Session = Depends(get_db)):
    if payload.is_default:
        db.query(BaseResume).filter(
            BaseResume.language == payload.language,
            BaseResume.is_default == True,  # noqa: E712
        ).update({"is_default": False})

    resume = BaseResume(
        name=payload.name,
        language=payload.language,
        is_default=payload.is_default,
        data=payload.data.model_dump(),
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/import", status_code=201)
async def import_resume(
    file: UploadFile = File(...),
    name: str = Form(...),
    language: str = Form("en"),
    is_default: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Import a CV from an uploaded PDF or a LinkedIn data-export ZIP.

    - **PDF** (`application/pdf` or `.pdf`): text is extracted with pypdf,
      then parsed into the CV schema by the configured LLM
      (Anthropic → OpenAI → heuristic fallback).
    - **ZIP** (`application/zip` or `.zip`): treated as a LinkedIn archive,
      parsed deterministically from the CSVs inside.

    The parsed CV is saved as a new BaseResume immediately; the user can
    then review and edit it in the Resume tab.

    Response includes a `summary` dict showing what got extracted (counts of
    positions, skills, etc.) so the UI can confirm the import worked.
    """
    # Read with size cap
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_BYTES // 1024 // 1024} MB)")
    if not content:
        raise HTTPException(400, "File is empty")

    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    is_pdf = filename.endswith(".pdf") or "pdf" in content_type
    is_zip = filename.endswith(".zip") or "zip" in content_type

    logger.info(
        "Resume import: filename=%r content_type=%r size=%d is_pdf=%s is_zip=%s",
        file.filename, file.content_type, len(content), is_pdf, is_zip,
    )

    parser_used = "linkedin"  # for ZIP path
    try:
        if is_pdf:
            text = extract_pdf_text(content)
            logger.info("Extracted %d chars from PDF", len(text))
            cv_dict, parser_used = await parse_cv_text_with_llm(text, language_hint=language)
            logger.info("CV parsed via %s", parser_used)
            source_type = "pdf"
        elif is_zip:
            cv_dict = parse_linkedin_archive(content)
            source_type = "linkedin"
        else:
            raise HTTPException(
                400,
                "Unsupported file type. Upload a PDF (your CV) or a ZIP "
                "(your LinkedIn data export).",
            )
    except CVImportError as e:
        logger.warning("CV import failed (CVImportError): %s", e)
        raise HTTPException(422, str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("CV import failed at parse step")
        raise HTTPException(500, f"Import failed: {e}") from e

    # Validate + fill defaults through Pydantic. If the LLM returned extra
    # keys that don't match the schema, drop them rather than 422-ing the
    # whole import — the user can fill in the gaps after.
    try:
        cv_dict = {k: v for k, v in (cv_dict or {}).items() if k in CVData.model_fields}
        cv = CVData(**cv_dict)
    except Exception as e:
        logger.exception("Parsed CV did not match schema; falling back to empty CV")
        cv = CVData(
            full_name=str(cv_dict.get("full_name") or ""),
            email=str(cv_dict.get("email") or ""),
            phone=str(cv_dict.get("phone") or ""),
            location=str(cv_dict.get("location") or ""),
            linkedin=str(cv_dict.get("linkedin") or ""),
            website=str(cv_dict.get("website") or ""),
            summary=str(cv_dict.get("summary") or ""),
        )

    # DB write — wrapped so a constraint violation or lock can't escape as a
    # bare 500 with no detail.
    try:
        if is_default:
            db.query(BaseResume).filter(
                BaseResume.language == language,
                BaseResume.is_default == True,  # noqa: E712
            ).update({"is_default": False})

        resume = BaseResume(
            name=name,
            language=language,
            is_default=is_default,
            data=cv.model_dump(),
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
    except Exception as e:
        db.rollback()
        logger.exception("CV import failed at DB write step")
        raise HTTPException(500, f"Could not save resume: {e}") from e

    return {
        "resume": BaseResumeOut.model_validate(resume).model_dump(),
        "source": source_type,
        "parser": parser_used,
        "summary": summarize_extracted(cv.model_dump()),
    }


@router.get("/{resume_id}", response_model=BaseResumeOut)
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(BaseResume).filter(BaseResume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")
    return resume


@router.patch("/{resume_id}", response_model=BaseResumeOut)
def update_resume(resume_id: int, payload: BaseResumeUpdate, db: Session = Depends(get_db)):
    resume = db.query(BaseResume).filter(BaseResume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")

    if payload.is_default:
        db.query(BaseResume).filter(
            BaseResume.language == resume.language,
            BaseResume.is_default == True,  # noqa: E712
            BaseResume.id != resume_id,
        ).update({"is_default": False})

    if payload.name is not None:
        resume.name = payload.name
    if payload.is_default is not None:
        resume.is_default = payload.is_default
    if payload.data is not None:
        resume.data = payload.data.model_dump()
        resume.version += 1

    db.commit()
    db.refresh(resume)
    return resume


@router.post("/{resume_id}/translate", response_model=BaseResumeOut, status_code=201)
async def translate_resume(
    resume_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Translate a CV to a different language via the configured LLM.

    Body: ``{"target_language": "en"|"pt", "name"?: str, "is_default"?: bool}``.
    Creates a NEW BaseResume row — the original stays untouched. By default
    names the result "<original> (target)" so the user can keep both side
    by side and pick whichever matches the job they're applying to.
    """
    target_lang = (payload.get("target_language") or "").lower()
    if not target_lang:
        raise HTTPException(400, "target_language is required (e.g. 'en' or 'pt')")

    src = db.query(BaseResume).filter(BaseResume.id == resume_id).first()
    if not src:
        raise HTTPException(404, "Resume not found")

    if src.language == target_lang:
        raise HTTPException(
            400,
            f"Resume is already in {target_lang}. Translation only makes sense across languages.",
        )

    try:
        translated_dict, parser_used = await translate_cv(
            src.data, target_lang, source_language=src.language,
        )
    except CVImportError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        logger.exception("Translation failed")
        raise HTTPException(500, f"Translation failed: {e}") from e

    # Validate through Pydantic; tolerate extra fields by trimming them.
    try:
        translated_dict = {k: v for k, v in (translated_dict or {}).items() if k in CVData.model_fields}
        cv = CVData(**translated_dict)
    except Exception as e:
        logger.exception("Translated CV did not match schema")
        raise HTTPException(422, f"Translation produced invalid shape: {e}") from e

    # Default name: "<original name> (EN)" trimming any existing "(PT)" suffix
    name = payload.get("name")
    if not name:
        base = src.name
        for suffix in (" (EN)", " (PT)", " (en)", " (pt)"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        name = f"{base} ({target_lang.upper()})"

    is_default = bool(payload.get("is_default", False))
    if is_default:
        db.query(BaseResume).filter(
            BaseResume.language == target_lang,
            BaseResume.is_default == True,  # noqa: E712
        ).update({"is_default": False})

    new_resume = BaseResume(
        name=name,
        language=target_lang,
        is_default=is_default,
        data=cv.model_dump(),
    )
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)
    logger.info(
        "Translated resume id=%d (%s) → new id=%d (%s) via %s",
        src.id, src.language, new_resume.id, target_lang, parser_used,
    )
    return new_resume


@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(BaseResume).filter(BaseResume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")
    if resume.is_default:
        raise HTTPException(400, "Cannot delete the default resume. Set another as default first.")
    db.delete(resume)
    db.commit()


# ── Application Templates ──────────────────────────────────────────────────────

@router.get("/templates", response_model=list[ApplicationTemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return db.query(ApplicationTemplate).order_by(ApplicationTemplate.language, ApplicationTemplate.name).all()


@router.get("/templates/{template_id}", response_model=ApplicationTemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(ApplicationTemplate).filter(ApplicationTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.patch("/templates/{template_id}", response_model=ApplicationTemplateOut)
def update_template(template_id: int, body: dict, db: Session = Depends(get_db)):
    t = db.query(ApplicationTemplate).filter(ApplicationTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    for field in ("name", "content", "is_default"):
        if field in body:
            setattr(t, field, body[field])
    db.commit()
    db.refresh(t)
    return t
