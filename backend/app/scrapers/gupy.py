"""Gupy scraper — uses Gupy's public JSON API (the main Brazilian job board)."""
import logging
import unicodedata
from datetime import datetime
from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

GUPY_API = "https://portal.api.gupy.io/api/v1/jobs"

# Gupy's `state` filter matches full names ("São Paulo"), not UF ("SP").
BR_UF_TO_STATE_NAME: dict[str, str] = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}


def _normalize_state_param(state: str) -> str:
    s = state.strip()
    if len(s) == 2 and s.isalpha():
        return BR_UF_TO_STATE_NAME.get(s.upper(), s)
    return s


def _api_job_name(query: str) -> str:
    """Gupy treats multi-word jobName as strict AND; combined with city it often returns zero.

    Use the first meaningful token so the API returns a broad set; scoring happens later in Carrera.
    """
    parts = query.strip().split()
    return parts[0] if parts else ""


def _city_matches(config_city: str, item_city: str) -> bool:
    if not config_city or not item_city:
        return True
    a = unicodedata.normalize("NFKD", config_city.casefold()).encode("ascii", "ignore").decode()
    b = unicodedata.normalize("NFKD", item_city.casefold()).encode("ascii", "ignore").decode()
    return a in b or b in a


def _state_matches(config_state: str, item_state: str) -> bool:
    if not config_state or not item_state:
        return True
    norm_cfg = _normalize_state_param(config_state)
    a = unicodedata.normalize("NFKD", norm_cfg.casefold()).encode("ascii", "ignore").decode()
    b = unicodedata.normalize("NFKD", item_state.casefold()).encode("ascii", "ignore").decode()
    return a == b or a in b or b in a


class GupyScraper(BaseScraper):
    source_type = "gupy"

    async def fetch(self) -> list[RawJob]:
        raw_query = self.config.get("search_query", "")
        city = (self.config.get("city") or "").strip()
        state = (self.config.get("state") or "").strip()

        api_name = _api_job_name(raw_query)

        async def one_request(use_city: bool, use_state: bool) -> list[dict]:
            params: dict = {"jobName": api_name, "limit": 25, "offset": 0}
            if use_city and city:
                params["city"] = city
            if use_state and state:
                params["state"] = _normalize_state_param(state)

            batch: list[dict] = []
            for offset in range(0, min(self.max_jobs * 3, 300), 25):
                params["offset"] = offset
                try:
                    resp = await self._get(GUPY_API, params=params)
                    data = resp.json()
                    rows = data.get("data") or []
                    if not rows:
                        break
                    batch.extend(rows)
                    if len(batch) >= self.max_jobs * 3:
                        break
                except Exception as e:
                    logger.warning(f"Gupy fetch error at offset={offset}: {e}")
                    break
            return batch

        # Broad fetch first (API returns 0 for multi-word jobName + geo very often)
        if not api_name:
            logger.warning("Gupy: empty search_query in source config")
            return []

        rows = await one_request(use_city=False, use_state=False)
        if city or state:
            filtered = [
                r
                for r in rows
                if _city_matches(city, (r.get("city") or "")) and _state_matches(state, (r.get("state") or ""))
            ]
            if filtered:
                rows = filtered
            elif rows:
                logger.info(
                    "Gupy: API returned jobs but none matched city/state filters; returning unfiltered results"
                )

        jobs: list[RawJob] = []
        for item in rows[: self.max_jobs]:
            try:
                url = item.get("jobUrl") or f"https://portal.gupy.io/job/{item.get('id', '')}"
                location_parts = [
                    item.get("city", ""),
                    item.get("state", ""),
                    item.get("country", "Brasil"),
                ]
                location = ", ".join(p for p in location_parts if p)

                workplace = item.get("workplaceType", "")
                remote = workplace.lower() in ("remote", "remoto", "hybrid", "hibrido") if workplace else None

                salary_range = item.get("salaryRange") or {}

                posted_raw = item.get("publishedDate") or item.get("createdAt")
                posted_at = None
                if posted_raw:
                    try:
                        posted_at = datetime.fromisoformat(posted_raw.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                jobs.append(
                    RawJob(
                        title=item.get("name", ""),
                        company=item.get("careerPageName") or item.get("companyName", ""),
                        location=location,
                        url=url,
                        description=item.get("description", ""),
                        salary_min=salary_range.get("from"),
                        salary_max=salary_range.get("to"),
                        currency="BRL",
                        remote=remote,
                        seniority=item.get("seniorityLevel"),
                        employment_type=item.get("type"),
                        posted_at=posted_at,
                    )
                )
            except Exception as e:
                logger.debug(f"Gupy item parse error: {e}")
                continue

        logger.info(f"Gupy: fetched {len(jobs)} jobs (api jobName='{api_name}', raw query='{raw_query}')")
        return jobs
