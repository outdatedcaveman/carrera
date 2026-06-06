"""Layer 3 of the autofill plan — drive a real browser to fill an ATS form.

Design (see ``docs/AUTOFILL_ROADMAP.md``):

- We use **Playwright with the user's installed system Chrome**
  (``channel="chrome"``) so we don't have to bundle Chromium and the user
  keeps their cookies / logins / extensions. Chromium is ~150MB; the
  user almost certainly has Chrome already.
- Browser launches in **headed** mode. The user watches what's typed and
  reviews before submitting. Carrera never clicks Submit — that's a
  human responsibility, both for legal-meaningful answers
  (work authorization, criminal record, etc.) and because every form
  has its own Submit button + confirmation flow we can't generalize.
- Field detection is **heuristic** in this first cut: we walk the form,
  read each input's labels (``<label for>``, aria-label, placeholder,
  surrounding text, ``name``/``id`` attribute), and pattern-match
  against a dictionary of known field types. Hits get filled from the
  user's Quick Answers + tailored CV. Misses get reported back so the
  user knows what to fill manually.
- Per-ATS adapters (Workday, Greenhouse, Lever, Ashby, Gupy,
  SmartRecruiters) and the LLM-driven fallback for unknown ATSes are
  on the roadmap but not in this PR. The heuristic alone should hit
  maybe 50-70% of fields on a generic Workday/Greenhouse, which is
  already a big time-saver vs. typing them all.

Flow per call:

1. Build a "fact dict" from the user's tailored CV + Quick Answers.
2. Launch Chrome via ``playwright.chromium.launch(channel="chrome")``.
3. Navigate to ``job.url``. Wait for first idle.
4. Find the visible form (largest form element by input count, or
   document body if no <form>).
5. For each visible input/select/textarea, classify it by label and
   attempt to fill it.
6. Try to upload the resume PDF if a file input matches CV-shaped
   labels.
7. Yield a per-field report. Leave the browser open with the page on
   screen — the user reviews and submits.

The whole thing runs in a worker thread so the FastAPI request
doesn't block. We stream progress back through a small in-process
queue keyed by application_id so the frontend can poll.
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


# ── Field-classification dictionary ───────────────────────────────────────────
# Maps a field type → list of regex patterns that match the field's label /
# aria-label / placeholder / name / id text. First-match wins. Patterns are
# case-insensitive substrings; word boundaries are used where ambiguity matters
# (eg. "name" vs "first name").

FIELD_PATTERNS: dict[str, list[str]] = {
    "first_name": [
        r"\bfirst\s*name\b", r"\bgiven\s*name\b", r"\bprimeiro\s*nome\b", r"^fname$", r"^first[_-]?name$",
    ],
    "last_name": [
        r"\blast\s*name\b", r"\bsurname\b", r"\bfamily\s*name\b", r"\bsobrenome\b", r"^lname$", r"^last[_-]?name$",
    ],
    "full_name": [
        r"\bfull\s*name\b", r"\byour\s*name\b", r"\bnome\s*completo\b", r"^name$", r"\bcandidate.*name\b",
    ],
    "email": [
        r"\be-?mail\b", r"^email$",
    ],
    "phone": [
        r"\bphone\b", r"\bmobile\b", r"\btelefone\b", r"\bcelular\b", r"\bcontact\s*number\b", r"^tel$",
    ],
    "linkedin": [
        r"\blinkedin\b", r"linked.?in.*url", r"linked.?in.*profile",
    ],
    "github": [
        r"\bgithub\b", r"\bportfolio.*url\b",
    ],
    "website": [
        r"\bwebsite\b", r"\bportfolio\b", r"\bpersonal\s*site\b", r"\bweb\s*page\b",
    ],
    "current_city": [
        r"\bcity\b", r"\bcidade\b", r"\bcurrent\s*city\b", r"\bcity.*reside\b",
    ],
    "current_country": [
        r"\bcountry\b", r"\bpa[ií]s\b",
    ],
    "current_location": [
        r"\blocation\b", r"\baddress\b", r"\bendere[çc]o\b", r"\bcurrent\s*location\b", r"\bwhere.*based\b",
    ],
    # Work authorization
    "auth_us": [
        r"authoriz.*work.*us", r"authoriz.*united\s*states", r"work.*permit.*us",
        r"legally.*work.*us", r"eligible.*work.*us",
    ],
    "auth_eu": [
        r"authoriz.*work.*eu", r"authoriz.*european", r"work.*permit.*eu",
        r"legally.*work.*eu", r"eu\s*work\s*permit",
    ],
    "auth_uk": [
        r"authoriz.*work.*uk", r"authoriz.*united\s*kingdom", r"right.*work.*uk",
    ],
    "auth_br": [
        r"authoriz.*work.*brazil", r"autoriz.*trabalh.*brasil", r"trabalh.*brasil",
    ],
    "sponsorship_required": [
        r"sponsor.*visa", r"require.*sponsor", r"need.*sponsor", r"visa.*sponsor",
        r"requir.*work.*authoriz", r"patroc[ií]nio",
    ],
    # Compensation
    "salary_expectation": [
        r"salary.*expect", r"expected.*salary", r"compensat.*expect", r"desired.*salary",
        r"sal[áa]rio.*pretend", r"pretens[ãa]o.*salar", r"target.*comp",
    ],
    # Logistics
    "notice_period": [
        r"notice\s*period", r"how\s*soon.*start", r"earliest.*start", r"available.*start",
        r"when.*can.*start", r"per[ií]odo.*aviso",
    ],
    "willing_to_relocate": [
        r"willing.*relocat", r"open.*relocat", r"relocate", r"realocar",
    ],
    "remote_preference": [
        r"work\s*arrangement", r"remote.*hybrid", r"work.*location.*pref",
    ],
    # Background
    "years_experience": [
        r"years.*experience", r"total.*experience", r"anos.*experi[êe]ncia",
    ],
    "highest_education": [
        r"highest.*degree", r"education.*level", r"highest.*education",
        r"escolaridade", r"forma[çc][ãa]o\s*acad",
    ],
    # Voluntary self-ID (US-style EEO)
    "eeo_gender": [
        r"^gender$", r"\bgender\b.*ident", r"sex$",
    ],
    "eeo_race": [
        r"\brace\b", r"\bethnic", r"\bra[çc]a\b",
    ],
    "eeo_veteran": [
        r"\bveteran\b", r"protected.*veteran",
    ],
    "eeo_disability": [
        r"\bdisability\b", r"defici[êe]ncia",
    ],
    # Free-text
    "why_role": [
        r"why.*interested.*role", r"why.*this.*role", r"why.*want.*join",
        r"why.*want.*work", r"motivat", r"por\s*que.*vaga",
    ],
    "cover_letter": [
        r"cover\s*letter", r"carta.*apresenta", r"motivation\s*letter",
        r"tell.*about.*yourself", r"introduc.*yourself",
        r"\babout\s*you\b\s*[-–—:]",  # "About you:" as a label, not a heading
    ],
    "resume_upload": [
        r"\bresume\b", r"\bcv\b", r"curr[ií]culo", r"upload.*resume", r"upload.*cv",
        r"attach.*resume", r"attach.*cv",
    ],
}


# Pre-compile for speed
_COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in FIELD_PATTERNS.items()}


def classify_field(label_text: str) -> str | None:
    """Return the field-type key whose patterns match ``label_text``, or None.

    ``label_text`` should be the concatenation of every label-like attribute
    we can scrape: <label for>, aria-label, placeholder, surrounding text,
    name/id attribute. The dict is checked in insertion order so more
    specific keys (first_name) match before generic ones (full_name).
    """
    text = label_text.strip().lower()
    if not text:
        return None
    for key, patterns in _COMPILED.items():
        for p in patterns:
            if p.search(text):
                return key
    return None


# ── Fact-dict builder ─────────────────────────────────────────────────────────

def build_facts(quick_answers: dict, cv_data: dict) -> dict[str, Any]:
    """Flatten the user's data into a string-keyed dict the filler can look up."""
    qa = quick_answers or {}
    cv = cv_data or {}
    ident = qa.get("identity") or {}
    auth = qa.get("work_auth") or {}
    comp = qa.get("compensation") or {}
    log = qa.get("logistics") or {}
    bg = qa.get("background") or {}
    eeo = qa.get("eeo") or {}

    # Split CV full_name into first / last for ATSes that demand them separate
    full_name = (ident.get("full_name") or cv.get("full_name") or "").strip()
    parts = full_name.split() if full_name else []
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""

    yes_no = {"yes": "Yes", "no": "No", "unsure": "I'm not sure"}

    salary_str = ""
    if comp.get("target_min_salary"):
        cur = comp.get("preferred_currency") or ""
        salary_str = f"{int(comp['target_min_salary']):,} {cur}".strip()

    facts = {
        "first_name": first,
        "last_name": last,
        "full_name": full_name,
        "email": ident.get("email") or cv.get("email", ""),
        "phone": ident.get("phone") or cv.get("phone", ""),
        "linkedin": ident.get("linkedin") or cv.get("linkedin", ""),
        "github": ident.get("github", ""),
        "website": ident.get("website") or cv.get("website", ""),
        "current_city": ident.get("current_city", ""),
        "current_country": ident.get("current_country", ""),
        "current_location": " ".join(p for p in [ident.get("current_city"), ident.get("current_country")] if p),
        "auth_us": yes_no.get(auth.get("authorized_us", ""), ""),
        "auth_eu": yes_no.get(auth.get("authorized_eu", ""), ""),
        "auth_uk": yes_no.get(auth.get("authorized_uk", ""), ""),
        "auth_br": yes_no.get(auth.get("authorized_br", ""), ""),
        "sponsorship_required": yes_no.get(auth.get("sponsorship_required", ""), ""),
        "salary_expectation": salary_str,
        "notice_period": f"{log['notice_period_weeks']} weeks" if log.get("notice_period_weeks") else "",
        "willing_to_relocate": {"yes": "Yes", "no": "No", "depends": "Depends on the role"}.get(log.get("willing_to_relocate", ""), ""),
        "remote_preference": log.get("remote_preference", ""),
        "years_experience": str(bg["total_years_experience"]) if bg.get("total_years_experience") else "",
        "highest_education": bg.get("highest_degree", ""),
        "eeo_gender": eeo.get("gender", ""),
        "eeo_race": eeo.get("race_ethnicity", ""),
        "eeo_veteran": eeo.get("veteran_status", ""),
        "eeo_disability": eeo.get("disability_status", ""),
    }
    # Drop blank entries so the filler doesn't try to type empty strings
    return {k: v for k, v in facts.items() if v}


# ── Browser-side filler ───────────────────────────────────────────────────────
# The actual DOM walk lives in JS so we can do it in one round-trip and don't
# have to ferry every node back into Python. We inject a function that returns
# a list of {selector, label_text, type, tag} for every visible input and
# accept fill instructions back.

DETECT_JS = r"""
() => {
  const out = [];
  // Returns { direct, nearby }. ``direct`` is label text we're highly
  // confident applies to *this specific* input (label-for, aria-label,
  // placeholder, name, id). ``nearby`` is the heuristic fallback (closest
  // preceding label, parent legend) we only use if ``direct`` matches
  // nothing — otherwise the form-level "First Name *" label leaks into
  // every other input on the page.
  const labelFor = (el) => {
    let direct = '';
    let nearby = '';
    const id = el.id;
    if (id) {
      const lbl = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (lbl) direct += ' ' + (lbl.innerText || '');
    }
    const closeLabel = el.closest('label');
    if (closeLabel && closeLabel !== el) direct += ' ' + (closeLabel.innerText || '');
    const aLabBy = el.getAttribute('aria-labelledby');
    if (aLabBy) {
      aLabBy.split(/\s+/).forEach(id2 => {
        const t = document.getElementById(id2);
        if (t) direct += ' ' + (t.innerText || '');
      });
    }
    direct += ' ' + (el.getAttribute('aria-label') || '');
    direct += ' ' + (el.getAttribute('placeholder') || '');
    direct += ' ' + (el.getAttribute('name') || '');
    direct += ' ' + (el.getAttribute('id') || '');
    direct += ' ' + (el.getAttribute('title') || '');

    // Nearby: the immediately-preceding label/legend in the DOM. Only used
    // as a fallback by the Python classifier.
    let prev = el.previousElementSibling;
    while (prev) {
      if (prev.tagName === 'LABEL' || prev.tagName === 'LEGEND') {
        nearby += ' ' + (prev.innerText || '');
        break;
      }
      prev = prev.previousElementSibling;
    }
    // Also grab a parent's <legend> if we're inside a fieldset
    const fs = el.closest('fieldset');
    if (fs) {
      const legend = fs.querySelector(':scope > legend');
      if (legend) nearby += ' ' + (legend.innerText || '');
    }
    return {
      direct: direct.replace(/\s+/g, ' ').trim().slice(0, 300),
      nearby: nearby.replace(/\s+/g, ' ').trim().slice(0, 300),
    };
  };
  const seen = new WeakSet();
  document.querySelectorAll('input, textarea, select').forEach((el, i) => {
    if (seen.has(el)) return;
    seen.add(el);
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return;
    const t = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (type === 'hidden' || type === 'submit' || type === 'button') return;
    let selector;
    if (el.id) {
      selector = '#' + CSS.escape(el.id);
    } else if (el.name) {
      selector = `${t}[name="${CSS.escape(el.name)}"]`;
    } else {
      const sibs = Array.from(el.parentElement?.children || []).filter(c => c.tagName === el.tagName);
      const idx = sibs.indexOf(el);
      selector = `${el.parentElement?.tagName.toLowerCase() || 'body'} > ${t}:nth-of-type(${idx + 1})`;
    }
    const labels = labelFor(el);
    out.push({
      selector,
      direct_label: labels.direct,
      nearby_label: labels.nearby,
      tag: t,
      type: type,
      current_value: el.value || '',
      options: t === 'select' ? Array.from(el.options).map(o => o.value || o.text) : null,
    });
  });
  return out;
}
"""


def classify_detected(detected: dict) -> str | None:
    """Two-pass classify: try the direct label first (label-for, aria-label,
    placeholder, name, id) and only fall back to nearby siblings if direct
    matches nothing. This avoids the form-level first-label-leaks-everywhere
    bug where every input on a flat form was classified as ``first_name``."""
    return classify_field(detected.get("direct_label", "")) or classify_field(detected.get("nearby_label", ""))


@dataclass
class FillReport:
    """Per-field result the UI shows after the autofill run."""
    field_type: str | None
    label: str
    selector: str
    value_filled: str | None
    status: str  # "filled" | "skipped_no_data" | "skipped_unknown" | "error"
    error: str | None = None


@dataclass
class AutofillRun:
    """In-process state for a single autofill run.

    Lives in ``_RUNS`` keyed by application_id. The FastAPI endpoint that
    starts a run kicks the actual browser work into a thread (Playwright sync
    is more reliable than async on Windows) and the UI polls a status
    endpoint that reads from this object.
    """
    application_id: int
    job_url: str
    status: str = "starting"  # starting | navigating | filling | done | error
    message: str = ""
    fields_total: int = 0
    fields_filled: int = 0
    reports: list[FillReport] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    error: str | None = None


_RUNS: dict[int, AutofillRun] = {}
_RUNS_LOCK = threading.Lock()


def get_run(application_id: int) -> AutofillRun | None:
    with _RUNS_LOCK:
        return _RUNS.get(application_id)


def to_dict(run: AutofillRun) -> dict:
    return {
        **asdict(run),
        "elapsed_s": round(time.time() - run.started_at, 1),
    }


# ── Main entry point — runs in a thread ──────────────────────────────────────

def _select_value(detected: dict, want: str) -> str | None:
    """For a <select>, find the option whose text best matches ``want``."""
    opts = detected.get("options") or []
    if not opts:
        return None
    want_l = want.lower()
    for o in opts:
        if o and want_l in (o or "").lower():
            return o
    # Yes/No special: also handle "True"/"False"
    if want_l == "yes":
        for o in opts:
            if (o or "").strip().lower() in ("yes", "true", "1"):
                return o
    if want_l == "no":
        for o in opts:
            if (o or "").strip().lower() in ("no", "false", "0"):
                return o
    return None


def _fill_one(page, detected: dict, value: str, resume_pdf: str | None) -> FillReport:
    sel = detected["selector"]
    field_type = classify_detected(detected)
    label_short = (detected.get("direct_label") or detected.get("nearby_label") or "")[:80]
    try:
        if detected["tag"] == "select":
            opt = _select_value(detected, value)
            if opt is None:
                return FillReport(field_type, label_short, sel, None,
                                  "skipped_no_data", "no matching option")
            page.select_option(sel, opt, timeout=3000)
            return FillReport(field_type, label_short, sel, opt, "filled")
        if detected["type"] == "file":
            if resume_pdf and field_type == "resume_upload":
                page.set_input_files(sel, resume_pdf, timeout=5000)
                return FillReport(field_type, label_short, sel, resume_pdf, "filled")
            return FillReport(field_type, label_short, sel, None,
                              "skipped_no_data", "file input but no matching file")
        if detected["type"] in ("checkbox", "radio"):
            # Best-effort: check if value looks affirmative
            if str(value).strip().lower() in ("yes", "true", "1"):
                page.check(sel, timeout=3000)
                return FillReport(field_type, label_short, sel, "checked", "filled")
            return FillReport(field_type, label_short, sel, None,
                              "skipped_no_data", f"value '{value}' not checkboxable")
        # Plain text input / textarea
        page.fill(sel, str(value), timeout=3000)
        return FillReport(field_type, label_short, sel, value, "filled")
    except Exception as e:
        return FillReport(field_type, label_short, sel, None, "error", str(e))


def run_autofill_thread(
    application_id: int,
    job_url: str,
    facts: dict[str, Any],
    resume_pdf_path: str | None,
) -> None:
    """Worker thread: open Chrome, fill what we can, leave the page open.

    The page stays open after this returns — the user reviews and submits.
    Playwright's ``launch`` (vs ``launch_persistent_context``) gives us a
    fresh profile so we don't pollute their normal Chrome session. The
    browser stays alive because we hold the ``Playwright`` context open;
    we close it explicitly only on error.
    """
    from playwright.sync_api import sync_playwright

    run = _RUNS[application_id]

    try:
        with sync_playwright() as p:
            run.status = "navigating"
            run.message = "Launching Chrome…"
            browser = p.chromium.launch(channel="chrome", headless=False)
            ctx = browser.new_context()
            page = ctx.new_page()

            run.message = f"Opening {job_url}"
            page.goto(job_url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass  # some pages never go idle; that's fine

            run.status = "filling"
            run.message = "Detecting form fields…"
            detected = page.evaluate(DETECT_JS)
            run.fields_total = len(detected)
            logger.info("autofill: detected %d fields on %s", len(detected), job_url)

            for d in detected:
                ftype = classify_detected(d)
                label_short = (d.get("direct_label") or d.get("nearby_label") or "")[:80]
                if not ftype:
                    run.reports.append(FillReport(
                        None, label_short, d["selector"], None,
                        "skipped_unknown", None,
                    ))
                    continue
                value = facts.get(ftype)
                if not value:
                    run.reports.append(FillReport(
                        ftype, label_short, d["selector"], None,
                        "skipped_no_data", None,
                    ))
                    continue
                report = _fill_one(page, d, value, resume_pdf_path)
                if report.status == "filled":
                    run.fields_filled += 1
                run.reports.append(report)
                run.message = f"Filled {run.fields_filled}/{run.fields_total}"

            run.status = "done"
            run.message = (
                f"Filled {run.fields_filled}/{run.fields_total} fields. "
                f"Review the form, fix anything wrong, then click Submit."
            )

            # Hold the browser open so the user can interact with it. We
            # poll on the run's status every 2s; when the user closes the
            # window or marks done from the UI, we exit.
            while True:
                time.sleep(2)
                if run.status == "user_closed":
                    break
                # Detect the user closing the window themselves
                try:
                    if page.is_closed():
                        run.status = "user_closed"
                        run.message = "Browser closed."
                        break
                except Exception:
                    run.status = "user_closed"
                    break
            try:
                browser.close()
            except Exception:
                pass
    except Exception as e:
        logger.exception("autofill run failed")
        run.status = "error"
        run.error = str(e)
        run.message = f"Failed: {e}"


def start_run(
    application_id: int,
    job_url: str,
    facts: dict[str, Any],
    resume_pdf_path: str | None,
) -> AutofillRun:
    """Spawn a thread for a new autofill run and return its state object."""
    with _RUNS_LOCK:
        run = AutofillRun(application_id=application_id, job_url=job_url)
        _RUNS[application_id] = run
    t = threading.Thread(
        target=run_autofill_thread,
        args=(application_id, job_url, facts, resume_pdf_path),
        daemon=True,
    )
    t.start()
    return run


def stop_run(application_id: int) -> bool:
    """Mark a run as user-closed so the worker thread can exit its hold loop."""
    run = get_run(application_id)
    if run and run.status not in ("done", "error"):
        run.status = "user_closed"
        return True
    if run and run.status == "done":
        run.status = "user_closed"
        return True
    return False
