"""Job scoring engine — rates each job against an active search profile."""
import re
import logging
from fuzzywuzzy import fuzz
from ..models import SearchProfile, JobScore
from ..scrapers.base import RawJob

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "title": 0.35,
    "location": 0.20,
    "salary": 0.15,
    "skills": 0.20,
    "seniority": 0.10,
}

CATEGORY_THRESHOLDS = {
    "strong_match": 0.75,
    "good_match": 0.55,
    "worth_a_look": 0.35,
}

BRAZIL_CITIES = {
    "são paulo", "sp", "rio de janeiro", "rj", "florianópolis", "sc",
    "curitiba", "pr", "belo horizonte", "mg", "porto alegre", "rs",
    "brasília", "df", "salvador", "ba", "recife", "pe", "fortaleza", "ce",
}

SENIORITY_LEVELS = {
    "intern": 1, "estágio": 1, "estagiário": 1,
    "junior": 2, "jr": 2, "júnior": 2,
    "pleno": 3, "mid": 3, "analyst": 3, "analista": 3,
    "senior": 4, "sr": 4, "sênior": 4,
    "lead": 5, "líder": 5, "especialista": 5,
    "manager": 6, "gerente": 6, "head": 6,
    "director": 7, "diretor": 7,
    "vp": 8, "executive": 8,
}


def score_job(raw: RawJob, profile: SearchProfile) -> tuple[float, str, list[JobScore]]:
    """Return (total_score 0-1, category, score_details)."""
    config = profile.config
    weights = {**DEFAULT_WEIGHTS, **config.get("scoring_weights", {})}

    scores: dict[str, dict] = {}

    # Title match
    title_score = _score_title(raw.title, config.get("titles", []))
    scores["title"] = {"raw": title_score, "weight": weights["title"], "details": {}}

    # Location match
    loc_score = _score_location(raw.location, raw.remote, config.get("locations", []), config.get("remote_preference", "any"))
    scores["location"] = {"raw": loc_score, "weight": weights["location"], "details": {}}

    # Salary match
    sal_score = _score_salary(raw.salary_min, raw.salary_max, raw.currency, config)
    scores["salary"] = {"raw": sal_score, "weight": weights["salary"], "details": {}}

    # Skills/keyword match
    skill_score, skill_details = _score_skills(
        raw.title + " " + raw.description,
        config.get("preferred_keywords", []),
        config.get("excluded_keywords", []),
    )
    scores["skills"] = {"raw": skill_score, "weight": weights["skills"], "details": skill_details}

    # Seniority match
    sen_score = _score_seniority(raw.title, raw.seniority)
    scores["seniority"] = {"raw": sen_score, "weight": weights["seniority"], "details": {}}

    total = sum(v["raw"] * v["weight"] for v in scores.values())
    total = min(1.0, max(0.0, total))

    category = "reach"
    for cat, threshold in CATEGORY_THRESHOLDS.items():
        if total >= threshold:
            category = cat
            break

    job_scores = [
        JobScore(
            dimension=dim,
            weight=v["weight"],
            raw_score=v["raw"],
            weighted_score=v["raw"] * v["weight"],
            details=v["details"],
        )
        for dim, v in scores.items()
    ]

    return total, category, job_scores


def _score_title(title: str, target_titles: list[str]) -> float:
    if not target_titles:
        return 0.6
    title_lower = title.lower()
    best = max(
        fuzz.partial_ratio(t.lower(), title_lower) / 100.0
        for t in target_titles
    )
    return best


def _score_location(location: str, remote: bool | None, target_locations: list[str], remote_pref: str) -> float:
    if remote is True:
        if remote_pref in ("remote", "any"):
            return 1.0
        elif remote_pref == "hybrid":
            return 0.7
        else:
            return 0.3

    loc_lower = location.lower()
    if "remote" in loc_lower or "remoto" in loc_lower:
        return 0.9 if remote_pref in ("remote", "any", "hybrid") else 0.4

    for target in target_locations:
        if target.lower() in loc_lower or loc_lower in target.lower():
            return 1.0
        if fuzz.partial_ratio(target.lower(), loc_lower) >= 80:
            return 0.85

    return 0.2


def _score_salary(sal_min: float | None, sal_max: float | None, currency: str, config: dict) -> float:
    if sal_min is None and sal_max is None:
        return 0.5  # unknown salary — neutral

    if currency == "BRL":
        target_min = config.get("salary_min_brl")
        target_max = config.get("salary_max_brl")
    else:
        target_min = config.get("salary_min_usd")
        target_max = config.get("salary_max_usd")

    if not target_min and not target_max:
        return 0.5

    job_mid = (sal_min or 0) + ((sal_max or sal_min or 0) - (sal_min or 0)) / 2

    if target_min and job_mid < target_min * 0.8:
        return 0.1
    if target_min and job_mid >= target_min:
        return 1.0 if (not target_max or job_mid <= target_max) else 0.8

    return 0.5


def _score_skills(text: str, preferred: list[str], excluded: list[str]) -> tuple[float, dict]:
    text_lower = text.lower()

    for kw in excluded:
        if kw.lower() in text_lower:
            return 0.0, {"excluded_keyword_matched": kw}

    if not preferred:
        return 0.6, {}

    matched = [kw for kw in preferred if kw.lower() in text_lower]
    ratio = len(matched) / len(preferred)
    return min(1.0, ratio * 2), {"matched": matched, "total_preferred": len(preferred)}


def _score_seniority(title: str, seniority: str | None) -> float:
    text = (title + " " + (seniority or "")).lower()
    level = None
    for keyword, lvl in SENIORITY_LEVELS.items():
        if keyword in text:
            level = lvl
            break

    if level is None:
        return 0.6  # unknown — neutral

    # Target profile is mid-senior (3-6 range is good)
    if 3 <= level <= 6:
        return 1.0
    if level == 2 or level == 7:
        return 0.5
    return 0.2
