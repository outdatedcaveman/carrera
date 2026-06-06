"""Import a user's CV from a PDF, a LinkedIn data-export ZIP, or raw text.

Design:

- **PDF path**: extract text via `pypdf`, then ask the configured LLM (same
  provider used for tailoring) to parse it into our `CVData` schema. Resumes
  vary wildly in layout, so heuristic parsers tend to fail; LLMs handle this
  well and the call is ~$0.001 on Haiku.

- **LinkedIn archive path**: LinkedIn lets users download their own profile as
  a ZIP via Settings → Data privacy → "Get a copy of your data". Inside are a
  handful of CSVs (`Profile.csv`, `Positions.csv`, etc.). We parse those
  deterministically — no LLM needed — and map them into `CVData`. This is
  the legitimate, TOS-safe way to "import from LinkedIn".

- **Plain text path** (fallback): same LLM prompt, for when the user pastes
  their CV text.

All three return a `dict` in the CVData shape. The endpoint layer wraps this
into a BaseResume row so the user can edit immediately in the UI.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import zipfile
from typing import Any

import httpx

from . import settings_store

logger = logging.getLogger(__name__)


class CVImportError(Exception):
    """Raised on any unrecoverable failure during CV import."""
    pass


# Target schema (mirrors backend/app/schemas.py :: CVData). Duplicated as a
# string so the LLM prompt is self-contained and doesn't drift when the
# Pydantic model changes.
CV_SCHEMA_HINT = """{
  "full_name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "linkedin": "string (URL)",
  "website": "string (URL)",
  "summary": "string (2-4 sentences)",
  "experience": [
    {
      "company": "string",
      "title": "string",
      "start_date": "YYYY-MM or YYYY",
      "end_date": "YYYY-MM or YYYY or null if current",
      "location": "string",
      "bullets": ["string", ...],
      "keywords": ["string", ...]
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "field": "string",
      "start_date": "YYYY-MM or YYYY",
      "end_date": "YYYY-MM or YYYY or null if ongoing",
      "notes": "string"
    }
  ],
  "skills": ["string", ...],
  "languages": [{"language": "string", "level": "Native|Fluent|Intermediate|Basic"}],
  "certifications": ["string", ...]
}"""


def _empty_cv() -> dict:
    return {
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "website": "",
        "summary": "",
        "experience": [],
        "education": [],
        "skills": [],
        "languages": [],
        "certifications": [],
        "extra_sections": {},
    }


# ── PDF path ──────────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF. Raises CVImportError on unreadable PDFs."""
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise CVImportError(
            "pypdf is not installed. Add it to requirements.txt: pypdf==6.7.0"
        ) from e

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        raise CVImportError(f"Could not open PDF: {e}") from e

    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or "")
        except Exception as e:
            logger.warning(f"PDF page {i} failed to extract: {e}")

    text = "\n\n".join(p.strip() for p in pages if p.strip())
    if len(text) < 50:
        raise CVImportError(
            "The PDF contained almost no extractable text. It might be a scanned "
            "image — try exporting as text PDF, or paste the content manually."
        )
    return text


# ── LLM path (text → structured CVData) ───────────────────────────────────────

async def parse_cv_text_with_llm(text: str, language_hint: str = "en") -> tuple[dict, str]:
    """Ask the configured LLM to parse raw CV text into CVData.

    Returns ``(cv_dict, parser)`` where parser is one of
    ``"anthropic" | "openai" | "heuristic"`` so callers can warn the user
    when only the heuristic ran (which only fills name/email/phone/linkedin).
    """
    anthropic_key = settings_store.get("anthropic_api_key")
    openai_key = settings_store.get("openai_api_key")

    if anthropic_key:
        try:
            return await _anthropic_parse(text, language_hint, anthropic_key), "anthropic"
        except Exception as e:
            logger.warning(f"Anthropic CV parse failed: {e}; falling back")

    if openai_key:
        try:
            return await _openai_parse(text, language_hint, openai_key), "openai"
        except Exception as e:
            logger.warning(f"OpenAI CV parse failed: {e}; falling back")

    # Last resort: heuristic parse from plain text
    logger.info("No LLM configured; using heuristic CV text parser")
    return _heuristic_parse(text), "heuristic"


def _build_parse_prompt(text: str, language_hint: str) -> str:
    return f"""You are a resume parser. Extract the candidate's CV data from the text below and return it as JSON matching this exact schema:

{CV_SCHEMA_HINT}

Rules:
- Return ONLY valid JSON. No prose before or after.
- If a field is missing in the source, use an empty string or empty array — never null except for `end_date` when the role/education is ongoing.
- Preserve the original language for bullets, summary, titles (likely {language_hint}).
- For experience bullets, keep them as standalone achievement statements (1 per entry). Do not merge paragraphs.
- For skills, only list discrete skills/technologies/tools. No full sentences.
- Date format: "YYYY-MM" if the month is known, otherwise "YYYY".
- If start_date is unknown, use empty string "".

## CV text

{text[:15000]}

## Output (JSON only)
"""


# ── Translation path (CVData → CVData in target language) ────────────────────

LANG_NAMES = {
    "en": "English",
    "pt": "Portuguese (Brazilian)",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}


async def translate_cv(cv: dict, target_language: str, source_language: str | None = None) -> tuple[dict, str]:
    """Translate every user-facing text field on a CVData dict into ``target_language``.

    Returns ``(translated_dict, parser_used)``. If no LLM key is configured,
    raises CVImportError — translation needs an LLM to produce results
    worth using; a regex fallback would be embarrassing.

    What gets translated:
    - ``summary``, ``experience[].title``, ``experience[].bullets``,
      ``education[].degree``, ``education[].field``, ``education[].notes``,
      ``skills``, ``certifications``, ``languages[].level``.
    What stays:
    - ``full_name``, ``email``, ``phone``, ``linkedin``, ``website``,
      ``experience[].company``, ``education[].institution`` — proper nouns.
    - ``experience[].start_date`` / ``end_date`` — already YYYY-MM.

    The LLM gets the entire CV JSON and returns the same shape; we then
    overwrite preserved fields from the original to guarantee proper-noun
    integrity even if the LLM tried to translate them.
    """
    target = LANG_NAMES.get(target_language, target_language)
    source = LANG_NAMES.get(source_language) if source_language else "the source language (auto-detect)"

    anthropic_key = settings_store.get("anthropic_api_key")
    openai_key = settings_store.get("openai_api_key")

    if not (anthropic_key or openai_key):
        raise CVImportError(
            "Translation requires an LLM. Set an Anthropic or OpenAI API key in Settings → AI Provider."
        )

    errors: list[str] = []

    if anthropic_key:
        try:
            translated = await _anthropic_translate(cv, target, source, anthropic_key)
            return _restore_proper_nouns(cv, translated), "anthropic"
        except CVImportError as e:
            logger.warning(f"Anthropic translation failed: {e}")
            errors.append(str(e))
        except Exception as e:
            logger.warning(f"Anthropic translation crashed: {e}")
            errors.append(f"Anthropic: {e}")

    if openai_key:
        try:
            translated = await _openai_translate(cv, target, source, openai_key)
            return _restore_proper_nouns(cv, translated), "openai"
        except CVImportError as e:
            logger.warning(f"OpenAI translation failed: {e}")
            errors.append(str(e))
        except Exception as e:
            logger.warning(f"OpenAI translation crashed: {e}")
            errors.append(f"OpenAI: {e}")

    # Surface the actual provider error(s) — never the generic "failed on all"
    # version, that hides the real reason and forces the user to read logs.
    raise CVImportError(" / ".join(errors) if errors else "No LLM provider succeeded.")


def _build_translate_prompt(cv: dict, target: str, source: str) -> str:
    return f"""You are a precise CV/résumé translator. Translate the following CV from {source} into {target}.

Rules:
- Return the SAME JSON shape exactly. No prose before or after, no markdown fences.
- Translate user-facing prose: summary, experience titles + bullets + keywords, education degree + field + notes, skills, certifications names where they're descriptions (not branded certs like "AWS Solutions Architect"), and language proficiency levels.
- DO NOT translate: full_name, email, phone, linkedin, website, company names, institution names, dates (start_date / end_date), URLs.
- Skill names: keep proper nouns (Python, Kubernetes, FastAPI). Translate descriptive skills ("gestão de projetos" → "project management").
- Language proficiency levels: translate to standard target-language phrasing ("Native" / "Fluent" / "Intermediate" / "Basic" in English; "Nativo" / "Fluente" / "Intermediário" / "Básico" in Portuguese).
- Preserve dates exactly (YYYY-MM or YYYY format).
- Match the register and tone of the original.

CV JSON:
{json.dumps(cv, ensure_ascii=False)}

Output (JSON only, same shape):"""


def _extract_anthropic_error(resp: "httpx.Response") -> str:
    """Pull a human-readable message out of an Anthropic error body.

    Anthropic returns ``{"type":"error","error":{"type":"...","message":"..."}}``.
    The message is what the user actually needs to see — "credit balance too low",
    "model not found", "invalid api key" — not "Client error '400 Bad Request'".
    """
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message")
        if msg:
            return msg
    except Exception:
        pass
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


def _extract_openai_error(resp: "httpx.Response") -> str:
    """Same idea for OpenAI: ``{"error":{"message":"...","type":"..."}}``."""
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message")
        if msg:
            return msg
    except Exception:
        pass
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


async def _anthropic_translate(cv: dict, target: str, source: str, api_key: str) -> dict:
    prompt = _build_translate_prompt(cv, target, source)
    model = settings_store.get("anthropic_model") or "claude-haiku-4-5-20251001"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 8000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if resp.status_code >= 400:
            raise CVImportError(f"Anthropic: {_extract_anthropic_error(resp)}")
        data = resp.json()
        raw = data["content"][0]["text"]
    return _merge_with_empty(_extract_json(raw))


async def _openai_translate(cv: dict, target: str, source: str, api_key: str) -> dict:
    prompt = _build_translate_prompt(cv, target, source)
    model = settings_store.get("openai_model") or "gpt-4o-mini"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 8000,
                "response_format": {"type": "json_object"},
            },
        )
        if resp.status_code >= 400:
            raise CVImportError(f"OpenAI: {_extract_openai_error(resp)}")
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
    return _merge_with_empty(_extract_json(raw))


def _restore_proper_nouns(original: dict, translated: dict) -> dict:
    """Overwrite proper-noun fields from the original onto the translated copy.

    Defends against an LLM that decided to "helpfully" translate company
    names ("Acme Corp" → "Acme Corporação") or institutions. Dates too —
    we don't want "Jan 2020" → "Janeiro 2020" sneaking into our YYYY-MM
    format.
    """
    PRESERVE_TOP = {"full_name", "email", "phone", "linkedin", "website"}
    out = dict(translated)
    for k in PRESERVE_TOP:
        if original.get(k):
            out[k] = original[k]

    # experience: preserve company + dates
    out_exp = list(out.get("experience") or [])
    orig_exp = original.get("experience") or []
    for i, e in enumerate(out_exp):
        if i < len(orig_exp):
            e["company"] = orig_exp[i].get("company") or e.get("company", "")
            e["start_date"] = orig_exp[i].get("start_date") or e.get("start_date", "")
            e["end_date"] = orig_exp[i].get("end_date") if "end_date" in orig_exp[i] else e.get("end_date")
    out["experience"] = out_exp

    # education: preserve institution + dates
    out_edu = list(out.get("education") or [])
    orig_edu = original.get("education") or []
    for i, e in enumerate(out_edu):
        if i < len(orig_edu):
            e["institution"] = orig_edu[i].get("institution") or e.get("institution", "")
            e["start_date"] = orig_edu[i].get("start_date") or e.get("start_date", "")
            e["end_date"] = orig_edu[i].get("end_date") if "end_date" in orig_edu[i] else e.get("end_date")
    out["education"] = out_edu

    return out


async def _anthropic_parse(text: str, language_hint: str, api_key: str) -> dict:
    prompt = _build_parse_prompt(text, language_hint)
    model = settings_store.get("anthropic_model") or "claude-haiku-4-5-20251001"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 8000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if resp.status_code >= 400:
            raise CVImportError(f"Anthropic: {_extract_anthropic_error(resp)}")
        data = resp.json()
        raw = data["content"][0]["text"]
    return _merge_with_empty(_extract_json(raw))


async def _openai_parse(text: str, language_hint: str, api_key: str) -> dict:
    prompt = _build_parse_prompt(text, language_hint)
    model = settings_store.get("openai_model") or "gpt-4o-mini"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,
                "response_format": {"type": "json_object"},
            },
        )
        if resp.status_code >= 400:
            raise CVImportError(f"OpenAI: {_extract_openai_error(resp)}")
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
    return _merge_with_empty(_extract_json(raw))


def _extract_json(raw: str) -> dict:
    """Pull the first JSON object out of an LLM response."""
    raw = raw.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise CVImportError("LLM did not return a JSON object")
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        raise CVImportError(f"LLM returned invalid JSON: {e}") from e


def _merge_with_empty(parsed: dict) -> dict:
    """Ensure every required key is present so downstream validators don't choke."""
    out = _empty_cv()
    for k, v in parsed.items():
        if k in out:
            out[k] = v
    return out


# ── LinkedIn archive path ─────────────────────────────────────────────────────

def parse_linkedin_archive(zip_bytes: bytes) -> dict:
    """Parse a LinkedIn data-export ZIP into CVData.

    LinkedIn's archive contains (approx.) these CSVs, all header-terminated:
    - Profile.csv: First Name, Last Name, Maiden Name, Address, Birth Date,
      Headline, Summary, Industry, Zip Code, Geo Location
    - Email Addresses.csv: Email Address, Confirmed, Primary
    - PhoneNumbers.csv: Extension, Number, Type
    - Positions.csv: Company Name, Title, Description, Location, Started On,
      Finished On
    - Education.csv: School Name, Start Date, End Date, Notes, Degree Name,
      Activities
    - Skills.csv: Name
    - Languages.csv: Name, Proficiency
    - Certifications.csv: Name, Url, Authority, Started On, Finished On,
      License Number

    Not all files exist in every archive. Missing files are just skipped.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise CVImportError(f"Not a valid ZIP file: {e}") from e

    # Build a lookup that's case-insensitive on file name, since LinkedIn has
    # been inconsistent (PhoneNumbers.csv vs Phone Numbers.csv etc.)
    name_map = {name.lower().rsplit("/", 1)[-1]: name for name in zf.namelist()}

    def read_csv(*candidates: str) -> list[dict]:
        for cand in candidates:
            path = name_map.get(cand.lower())
            if path:
                try:
                    with zf.open(path) as f:
                        # LinkedIn exports are UTF-8 BOM
                        txt = f.read().decode("utf-8-sig", errors="replace")
                    reader = csv.DictReader(io.StringIO(txt))
                    return [row for row in reader]
                except Exception as e:
                    logger.warning(f"Failed to read {cand}: {e}")
                    return []
        return []

    cv = _empty_cv()

    # Profile
    profile_rows = read_csv("Profile.csv")
    if profile_rows:
        p = profile_rows[0]
        first = (p.get("First Name") or "").strip()
        last = (p.get("Last Name") or "").strip()
        cv["full_name"] = f"{first} {last}".strip()
        cv["summary"] = (p.get("Summary") or "").strip()
        # Location
        geo = (p.get("Geo Location") or p.get("Address") or "").strip()
        cv["location"] = geo

    # Email + phone
    for row in read_csv("Email Addresses.csv"):
        if row.get("Primary", "").lower() in ("yes", "true", "1"):
            cv["email"] = (row.get("Email Address") or "").strip()
            break
    if not cv["email"]:
        emails = read_csv("Email Addresses.csv")
        if emails:
            cv["email"] = (emails[0].get("Email Address") or "").strip()

    phones = read_csv("PhoneNumbers.csv", "Phone Numbers.csv")
    if phones:
        num = (phones[0].get("Number") or "").strip()
        if num:
            cv["phone"] = num

    # Positions
    positions = read_csv("Positions.csv")
    for row in positions:
        desc = (row.get("Description") or "").strip()
        # Split description into bullets on newlines / semicolons / bullet glyphs
        raw_bullets = [b.strip(" \t-•·–—") for b in re.split(r"[\r\n;•·–—]+", desc)]
        bullets = [b for b in raw_bullets if len(b) > 3]
        cv["experience"].append({
            "company": (row.get("Company Name") or "").strip(),
            "title": (row.get("Title") or "").strip(),
            "start_date": _normalize_linkedin_date(row.get("Started On")),
            "end_date": _normalize_linkedin_date(row.get("Finished On")) or None,
            "location": (row.get("Location") or "").strip(),
            "bullets": bullets,
            "keywords": [],
        })

    # Education
    for row in read_csv("Education.csv"):
        cv["education"].append({
            "institution": (row.get("School Name") or "").strip(),
            "degree": (row.get("Degree Name") or "").strip(),
            "field": (row.get("Activities") or "").strip(),
            "start_date": _normalize_linkedin_date(row.get("Start Date")),
            "end_date": _normalize_linkedin_date(row.get("End Date")) or None,
            "notes": (row.get("Notes") or "").strip(),
        })

    # Skills
    skill_rows = read_csv("Skills.csv")
    cv["skills"] = [(r.get("Name") or "").strip() for r in skill_rows if r.get("Name")]

    # Languages
    for row in read_csv("Languages.csv"):
        name = (row.get("Name") or "").strip()
        prof = (row.get("Proficiency") or "").strip()
        if name:
            cv["languages"].append({"language": name, "level": prof or "Fluent"})

    # Certifications
    cert_rows = read_csv("Certifications.csv")
    cv["certifications"] = [
        f"{(r.get('Name') or '').strip()}" +
        (f" — {r.get('Authority')}" if r.get("Authority") else "")
        for r in cert_rows if r.get("Name")
    ]

    if not cv["full_name"] and not cv["experience"]:
        raise CVImportError(
            "ZIP did not look like a LinkedIn data export — no Profile.csv "
            "or Positions.csv found inside."
        )

    return cv


def _normalize_linkedin_date(raw: str | None) -> str:
    """LinkedIn date formats: 'Jan 2020', '2020', 'Jan 01, 2020'. Normalize to YYYY-MM or YYYY."""
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""

    # "Jan 2020" or "January 2020"
    m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", raw)
    if m:
        month_names = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
            "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
            "january": "01", "february": "02", "march": "03", "april": "04",
            "june": "06", "july": "07", "august": "08", "september": "09",
            "october": "10", "november": "11", "december": "12",
        }
        mm = month_names.get(m.group(1).lower(), "")
        return f"{m.group(2)}-{mm}" if mm else m.group(2)

    # bare year
    if re.match(r"^\d{4}$", raw):
        return raw

    # ISO
    m = re.match(r"^(\d{4})-(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # fall back to whatever we got
    return raw


# ── Heuristic fallback ────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{2,3}\)?[\s\-.]?)?\d{3,5}[\s\-.]?\d{4}")
URL_RE = re.compile(r"https?://\S+", re.I)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/\S+", re.I)


SECTION_HEADERS = {
    "experience": [
        "experience", "work experience", "professional experience",
        "employment history", "career history",
        "experiência", "experiência profissional", "experiencia",
    ],
    "education": [
        "education", "academic background", "academic", "qualifications",
        "educação", "formação", "formação acadêmica",
    ],
    "skills": [
        "skills", "technical skills", "competencies", "core competencies",
        "habilidades", "competências",
    ],
    "languages": [
        "languages", "idiomas",
    ],
    "certifications": [
        "certifications", "certificates", "awards", "honors",
        "certificações", "certificados", "prêmios", "distinções",
    ],
}

# Bullet glyphs and common dash/list openers used in CVs
BULLET_RE = re.compile(r"^\s*(?:[•·▪◦‣⁃■◆▶▷▸►–—-]|\*|\d+[.)])\s+")
# A "date range" is two date markers connected by a dash or "to"/"–"/"—".
# A date marker is YYYY, YYYY-MM, or "Mon YYYY" / "Month YYYY". The right side
# can also be "Present" / "Current" / "Atual".
_MONTH_NAMES = (
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
    r"January|February|March|April|June|July|August|September|October|November|December|"
    r"Jan\.|Fev|Fev\.|Fevereiro|Mar\.|Março|Abr|Abr\.|Abril|Mai|Maio|Jun\.|Junho|"
    r"Jul\.|Julho|Ago|Ago\.|Agosto|Set|Set\.|Setembro|Out|Out\.|Outubro|Nov\.|Novembro|Dez|Dez\.|Dezembro)"
)
_DATE_TOKEN = rf"(?:{_MONTH_NAMES}\s+)?(?:19|20)\d{{2}}(?:[-/.]\d{{1,2}})?"
DATE_RANGE_RE = re.compile(
    rf"\b{_DATE_TOKEN}\s*(?:[-–—]|to|até)\s*(?:{_DATE_TOKEN}|present|current|now|atual|presente)\b",
    re.I,
)


def _classify_line(line: str) -> str | None:
    """If this line is a section header, return the canonical section name."""
    t = line.strip().rstrip(":").lower()
    if not t or len(t) > 50:
        return None
    for canon, aliases in SECTION_HEADERS.items():
        if t in aliases:
            return canon
    return None


def _heuristic_parse(text: str) -> dict:
    """Best-effort regex/heuristic CV parse for when no LLM is configured.

    This is a fallback — the LLM path produces dramatically better structure.
    But "no LLM key configured" is the most common case for first-time users,
    and getting *something* extracted (even rough experience entries) beats
    leaving the whole CV empty. We split the text by section headers, then
    inside each section we group lines into entries by date-range presence.
    """
    cv = _empty_cv()

    email_m = EMAIL_RE.search(text)
    if email_m:
        cv["email"] = email_m.group(0)

    phone_m = PHONE_RE.search(text)
    if phone_m:
        cv["phone"] = phone_m.group(0).strip()

    linkedin_m = LINKEDIN_RE.search(text)
    if linkedin_m:
        cv["linkedin"] = linkedin_m.group(0)

    lines = [l.rstrip() for l in text.splitlines()]

    # Name: first non-empty short line with no @ or digits (typically the header)
    for line in lines:
        s = line.strip()
        if 3 < len(s) < 60 and not re.search(r"[@/\d]", s):
            cv["full_name"] = s
            break

    # Sectionize: walk lines, switch buckets when we hit a known header
    sections: dict[str, list[str]] = {k: [] for k in SECTION_HEADERS}
    sections["_preamble"] = []
    current = "_preamble"
    for line in lines:
        cls = _classify_line(line)
        if cls is not None:
            current = cls
            continue
        sections[current].append(line)

    # Summary: first paragraph in preamble that's > 60 chars
    for line in sections["_preamble"]:
        s = line.strip()
        if len(s) >= 60:
            cv["summary"] = s
            break

    # Experience: split on lines containing a date-range; everything between
    # two date-range lines (or to the next section) is one entry.
    cv["experience"] = _heuristic_experience(sections.get("experience", []))
    cv["education"] = _heuristic_education(sections.get("education", []))

    # Skills: split on commas/semicolons/bullets
    skills_blob = "\n".join(sections.get("skills", []))
    if skills_blob.strip():
        # Try comma-split first (most common), fall back to newline
        candidates = [
            s.strip(" \t-•·–—:")
            for s in re.split(r"[,;\n•·]", skills_blob)
        ]
        cv["skills"] = [c for c in candidates if 1 < len(c) < 60]

    # Languages: lines like "English — Native" or "Portuguese: Fluent"
    for line in sections.get("languages", []):
        s = line.strip(" \t-•·–—")
        if not s:
            continue
        m = re.match(r"^([A-Za-zÀ-ÿ ]+?)\s*[—\-:]\s*([A-Za-zÀ-ÿ ]+)$", s)
        if m:
            cv["languages"].append({
                "language": m.group(1).strip(),
                "level": m.group(2).strip().title(),
            })

    # Certifications: each non-empty line is one entry
    for line in sections.get("certifications", []):
        s = line.strip(" \t-•·–—")
        if 4 < len(s) < 200:
            cv["certifications"].append(s)

    return cv


def _heuristic_experience(lines: list[str]) -> list[dict]:
    """Group experience-section lines into entries by date-range markers."""
    entries: list[dict] = []
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        entry = _build_experience_entry(current_lines)
        if entry:
            entries.append(entry)

    for line in lines:
        # A header line for a new role typically contains a date range
        if DATE_RANGE_RE.search(line) and current_lines:
            flush()
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()

    return entries


def _build_experience_entry(lines: list[str]) -> dict | None:
    """Take a chunk of lines belonging to one role and parse out fields."""
    # First line with a date range = the header
    header_idx = next(
        (i for i, l in enumerate(lines) if DATE_RANGE_RE.search(l)), 0
    )
    header_line = lines[header_idx].strip() if lines else ""
    if not header_line.strip() and not any(l.strip() for l in lines):
        return None

    # Pull dates out of the header
    start = ""
    end: str | None = None
    m = DATE_RANGE_RE.search(header_line)
    if m:
        chunk = m.group(0)
        years = re.findall(r"(?:19|20)\d{2}(?:[-/.]\d{1,2})?", chunk)
        if years:
            start = years[0].replace("/", "-").replace(".", "-")
        if len(years) > 1:
            end = years[1].replace("/", "-").replace(".", "-")
        elif re.search(r"\b(present|current|atual|presente)\b", chunk, re.I):
            end = None
        # Strip the date chunk out of header_line so we can parse company/title
        header_line = DATE_RANGE_RE.sub("", header_line).strip(" -–—|,\t")

    # Header is something like "Senior Engineer — Acme Corp" or "Acme Corp | Senior Engineer"
    title = company = ""
    parts = re.split(r"\s+(?:[—–\-|@]|at|na|no)\s+", header_line, maxsplit=1)
    if len(parts) == 2:
        title, company = parts[0].strip(), parts[1].strip()
    else:
        title = header_line

    # Bullets: lines after the header that look like bullets or substantial text
    bullets: list[str] = []
    for l in lines[header_idx + 1:]:
        s = l.strip()
        if not s:
            continue
        # Strip bullet glyphs
        cleaned = BULLET_RE.sub("", s).strip(" \t-•·–—")
        if 4 < len(cleaned) < 400:
            bullets.append(cleaned)

    if not (title or company or bullets):
        return None
    return {
        "company": company,
        "title": title,
        "start_date": start,
        "end_date": end,
        "location": "",
        "bullets": bullets,
        "keywords": [],
    }


def _heuristic_education(lines: list[str]) -> list[dict]:
    """Group education-section lines into entries by date markers."""
    entries: list[dict] = []
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        entry = _build_education_entry(current_lines)
        if entry:
            entries.append(entry)

    for line in lines:
        if (DATE_RANGE_RE.search(line) or re.search(r"\b(?:19|20)\d{2}\b", line)) and current_lines:
            flush()
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()
    return entries


def _build_education_entry(lines: list[str]) -> dict | None:
    text = " | ".join(l.strip() for l in lines if l.strip())
    if not text:
        return None
    # Try to find dates
    start = ""
    end: str | None = None
    m = DATE_RANGE_RE.search(text)
    if m:
        years = re.findall(r"(?:19|20)\d{2}", m.group(0))
        if years:
            start = years[0]
        if len(years) > 1:
            end = years[1]
    # First line likely contains institution + degree
    first = lines[0].strip() if lines else ""
    parts = re.split(r"\s+(?:[—–\-|,]|at|na|no)\s+", first, maxsplit=1)
    institution = parts[0].strip() if parts else first
    degree = parts[1].strip() if len(parts) > 1 else ""
    return {
        "institution": institution,
        "degree": degree,
        "field": "",
        "start_date": start,
        "end_date": end,
        "notes": " ".join(lines[1:]).strip() if len(lines) > 1 else "",
    }


# ── Counter summary for the API response ──────────────────────────────────────

def summarize_extracted(cv: dict) -> dict:
    return {
        "full_name": bool(cv.get("full_name")),
        "email": bool(cv.get("email")),
        "phone": bool(cv.get("phone")),
        "summary": bool(cv.get("summary")),
        "experience_count": len(cv.get("experience") or []),
        "education_count": len(cv.get("education") or []),
        "skills_count": len(cv.get("skills") or []),
        "languages_count": len(cv.get("languages") or []),
        "certifications_count": len(cv.get("certifications") or []),
    }
