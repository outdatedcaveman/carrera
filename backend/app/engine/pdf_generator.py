"""PDF generation for tailored resumes and cover letters using ReportLab."""
import html
import logging
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from ..config import get_settings
from ..models import Job

logger = logging.getLogger(__name__)
settings = get_settings()


def _e(s) -> str:
    """Escape user-provided text for reportlab's Paragraph parser.

    Paragraph treats its input as a tiny XML/HTML dialect — any literal
    ``<``, ``>``, or ``&`` in user content (job titles like "C/C++ Engineer",
    bullets with "&" or "<", URLs with query params) confuses the parser
    and either throws or, on some Windows reportlab versions, hangs the
    render. Always run user strings through this before f-string'ing them
    into a Paragraph template.
    """
    return html.escape(str(s or ""), quote=False)

ACCENT = colors.HexColor("#2563EB")  # blue-600
DARK = colors.HexColor("#1E293B")
GRAY = colors.HexColor("#64748B")
LIGHT_GRAY = colors.HexColor("#F1F5F9")


def _ensure_output_dir() -> Path:
    out = Path(settings.pdf_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def generate_resume_pdf(cv_data: dict, application_id: int) -> Path | None:
    try:
        out_dir = _ensure_output_dir()
        filename = out_dir / f"resume_{application_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        _build_resume_pdf(cv_data, str(filename))
        return filename
    except Exception as e:
        logger.error(f"PDF generation error (resume): {e}")
        return None


def generate_cover_letter_pdf(text: str, job: Job, application_id: int) -> Path | None:
    try:
        out_dir = _ensure_output_dir()
        filename = out_dir / f"cover_letter_{application_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        _build_cover_letter_pdf(text, job, str(filename))
        return filename
    except Exception as e:
        logger.error(f"PDF generation error (cover letter): {e}")
        return None


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=22, textColor=DARK, spaceAfter=2, alignment=TA_LEFT),
        "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=9, textColor=GRAY, spaceAfter=8, alignment=TA_LEFT),
        "section_title": ParagraphStyle("section_title", fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT, spaceBefore=10, spaceAfter=4, alignment=TA_LEFT),
        "role_title": ParagraphStyle("role_title", fontName="Helvetica-Bold", fontSize=10, textColor=DARK, spaceBefore=6, spaceAfter=1),
        "role_meta": ParagraphStyle("role_meta", fontName="Helvetica-Oblique", fontSize=9, textColor=GRAY, spaceAfter=3),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.5, textColor=DARK, leftIndent=10, spaceAfter=2, leading=13, bulletIndent=0, alignment=TA_JUSTIFY),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, textColor=DARK, spaceAfter=6, leading=14, alignment=TA_JUSTIFY),
        "skills": ParagraphStyle("skills", fontName="Helvetica", fontSize=9.5, textColor=DARK, spaceAfter=4),
    }


def _build_resume_pdf(cv: dict, filepath: str):
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
    )
    s = _styles()
    story = []

    # Header
    story.append(Paragraph(_e(cv.get("full_name", "")), s["name"]))
    contact_parts = [_e(p) for p in [cv.get("email"), cv.get("phone"), cv.get("location"), cv.get("linkedin")] if p]
    story.append(Paragraph(" · ".join(contact_parts), s["contact"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceAfter=6))

    # Summary
    if cv.get("summary"):
        story.append(Paragraph("SUMMARY" if _detect_lang(cv) == "en" else "RESUMO PROFISSIONAL", s["section_title"]))
        story.append(Paragraph(_e(cv["summary"]), s["body"]))

    # Experience
    if cv.get("experience"):
        story.append(Paragraph("EXPERIENCE" if _detect_lang(cv) == "en" else "EXPERIÊNCIA PROFISSIONAL", s["section_title"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=4))

        for exp in cv["experience"]:
            end = exp.get("end_date") or ("Present" if _detect_lang(cv) == "en" else "Atual")
            dates = f"{_e(exp.get('start_date', ''))} – {_e(end)}"
            story.append(Paragraph(f"{_e(exp.get('title', ''))} <font color='#64748B'>| {_e(exp.get('company', ''))}</font>", s["role_title"]))
            story.append(Paragraph(f"{dates}{' · ' + _e(exp.get('location', '')) if exp.get('location') else ''}", s["role_meta"]))
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"• {_e(bullet)}", s["bullet"]))
            story.append(Spacer(1, 4))

    # Education
    if cv.get("education"):
        story.append(Paragraph("EDUCATION" if _detect_lang(cv) == "en" else "FORMAÇÃO ACADÊMICA", s["section_title"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=4))

        for edu in cv["education"]:
            end = edu.get("end_date") or ("Present" if _detect_lang(cv) == "en" else "Atual")
            degree_field = f"{_e(edu.get('degree', ''))}"
            if edu.get("field"):
                degree_field += f" in {_e(edu.get('field', ''))}"
            story.append(Paragraph(f"{degree_field} <font color='#64748B'>| {_e(edu.get('institution', ''))}</font>", s["role_title"]))
            story.append(Paragraph(f"{_e(edu.get('start_date', ''))} – {_e(end)}", s["role_meta"]))
            if edu.get("notes"):
                story.append(Paragraph(_e(edu["notes"]), s["body"]))

    # Skills & Languages
    col1, col2 = [], []
    if cv.get("skills"):
        col1.append(Paragraph("SKILLS" if _detect_lang(cv) == "en" else "COMPETÊNCIAS", s["section_title"]))
        col1.append(Paragraph(_e(", ".join(cv["skills"])), s["skills"]))

    if cv.get("languages"):
        col2.append(Paragraph("LANGUAGES" if _detect_lang(cv) == "en" else "IDIOMAS", s["section_title"]))
        lang_lines = [f"{_e(l.get('language', ''))}: {_e(l.get('level', ''))}" for l in cv["languages"]]
        col2.append(Paragraph(" · ".join(lang_lines), s["skills"]))

    if col1 or col2:
        t = Table([[col1, col2]], colWidths=["55%", "45%"])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)

    doc.build(story)


def _build_cover_letter_pdf(text: str, job: Job, filepath: str):
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
    )
    s = _styles()
    story = []

    story.append(Paragraph(
        f"Application for: {_e(job.title)} at {_e(job.company)}",
        ParagraphStyle(
            "header", fontName="Helvetica-Bold", fontSize=12, textColor=ACCENT, spaceAfter=20,
        ),
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=20))

    for para in text.split("\n\n"):
        if para.strip():
            # Escape user content first, then re-introduce <br/> as the only
            # markup we actually want.
            escaped = _e(para.strip()).replace("\n", "<br/>")
            story.append(Paragraph(escaped, s["body"]))
            story.append(Spacer(1, 8))

    doc.build(story)


def _detect_lang(cv: dict) -> str:
    langs = cv.get("languages", [])
    for l in langs:
        if "Português" in l.get("language", "") or "Portuguese" in l.get("language", ""):
            if "Native" in l.get("level", "") or "Nativo" in l.get("level", ""):
                return "pt" if any("Português" in (x.get("language", "")) for x in langs) else "en"
    return "en"
