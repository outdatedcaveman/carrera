"""LinkedIn jobs scraper.

The legacy guest JSON endpoint (`/jobs-guest/jobs/api/seeMoreJobPostings/search`)
is dead — it now returns a 26-byte empty HTML stub for anonymous clients,
regardless of IP, cookies, or TLS fingerprint.

We have two working paths:

1. **Public HTML search** (default, no credentials): curl_cffi impersonating
   Chrome hits the regular `/jobs/search/` page. It renders 50–60 cards per
   request with the familiar `.base-search-card__*` classes, and supports
   pagination via `&start=N`. This is TOS-gray but the same surface Google
   sees when it indexes LinkedIn jobs.

2. **Authenticated voyager API** (opt-in, user provides a session cookie):
   if the source config contains `session_cookie` (the user pastes their
   `li_at` value from their browser), the scraper switches to the internal
   search API and gets richer data. This violates LinkedIn's TOS — we surface
   that in the UI.
"""
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from .base import BaseScraper, RawJob, ScraperBlockedError

logger = logging.getLogger(__name__)


SENIORITY_MAP = {
    "Internship": "intern",
    "Entry level": "junior",
    "Associate": "junior",
    "Mid-Senior level": "senior",
    "Director": "director",
    "Executive": "executive",
}

# Browser-ish headers. curl_cffi also sets TLS/HTTP2 fingerprints for us,
# so the above-the-wire request looks like Chrome 124.
PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _looks_blocked(html: str) -> bool:
    """Detect LinkedIn's short-circuit responses.

    - The legacy guest API returns `<!DOCTYPE html>\\n<!---->` (~26 bytes).
    - The authwall redirect serves a login page with "authwall" in the body.
    - Some flagged requests get a skeletal page without any job cards.
    """
    if html is None:
        return True
    stripped = html.strip()
    if len(stripped) < 200 and "<li" not in stripped.lower():
        return True
    low = stripped[:4096].lower()
    if "authwall" in low or "sign in to linkedin" in low:
        return True
    return False


class LinkedInScraper(BaseScraper):
    source_type = "linkedin"

    BASE_URL = "https://www.linkedin.com/jobs/search/"

    EXPERIENCE_CODES = {
        "intern": "1",
        "entry": "2",
        "associate": "3",
        "mid-senior": "4",
        "director": "5",
        "executive": "6",
    }

    async def fetch(self) -> list[RawJob]:
        query = (self.config.get("search_query") or "").strip()
        location = (self.config.get("location") or "Brazil").strip()
        filters = self.config.get("filters", {}) or {}
        session_cookie = (self.config.get("session_cookie") or "").strip()

        base_params: dict = {"keywords": query, "location": location}

        exp_levels = filters.get("experience_level", []) or []
        if exp_levels:
            codes = ",".join(self.EXPERIENCE_CODES.get(l, "4") for l in exp_levels)
            base_params["f_E"] = codes

        # Multi-word AND queries often return zero results. Try progressively
        # broader variants: full filters → drop f_E → drop all but first term.
        variants: list[dict] = [dict(base_params)]
        if base_params.get("f_E"):
            variants.append({k: v for k, v in base_params.items() if k != "f_E"})
        first_term = query.split()[0] if query else ""
        if first_term and first_term != query:
            variants.append({"keywords": first_term, "location": location})

        jobs: list[RawJob] = []
        blocked_variants = 0

        async with self._browser_session() as session:
            # Warm cookies
            try:
                await self._browser_pause()
                await session.get("https://www.linkedin.com/jobs/", headers=PAGE_HEADERS)
            except Exception as e:
                logger.debug(f"LinkedIn warmup failed (non-fatal): {e}")

            for variant in variants:
                jobs.clear()
                variant_blocked = False

                for start in range(0, min(self.max_jobs, 100), 25):
                    req_params = {**variant, "start": start}
                    req_headers = dict(PAGE_HEADERS)
                    if session_cookie:
                        # User-opted-in authenticated session. We send only the
                        # li_at cookie; curl_cffi will attach the rest from the
                        # warmup. This violates LinkedIn's TOS — caller is
                        # responsible for the account risk.
                        req_headers["Cookie"] = f"li_at={session_cookie}"

                    try:
                        await self._browser_pause()
                        resp = await session.get(self.BASE_URL, params=req_params, headers=req_headers)
                    except Exception as e:
                        logger.warning(f"LinkedIn fetch error at start={start}: {e}")
                        break

                    text = getattr(resp, "text", "") or ""
                    if _looks_blocked(text) and start == 0:
                        variant_blocked = True
                        break

                    page_jobs = self._parse_listing_page(text)
                    if not page_jobs:
                        break
                    jobs.extend(page_jobs)
                    if len(jobs) >= self.max_jobs:
                        break

                if variant_blocked:
                    blocked_variants += 1
                if jobs:
                    break

        if not jobs and blocked_variants == len(variants):
            raise ScraperBlockedError(
                "LinkedIn returned authwall or empty HTML for all query variants. "
                "The public search page refused this session — try again later, "
                "or paste a `session_cookie` (li_at) in the source config to use "
                "an authenticated fetch path."
            )

        logger.info(f"LinkedIn: fetched {len(jobs)} jobs for query='{query}'")
        return jobs[: self.max_jobs]

    def _parse_listing_page(self, html: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[RawJob] = []

        # New and old LinkedIn markups both use base-search-card__title. Walk
        # the card divs directly — some layouts don't wrap them in <li>.
        cards = soup.select("div.base-search-card, li div.base-search-card, li")
        seen: set[str] = set()

        for card in cards:
            try:
                title_el = card.select_one(".base-search-card__title")
                company_el = card.select_one(".base-search-card__subtitle")
                location_el = card.select_one(".job-search-card__location")
                link_el = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")
                time_el = card.select_one("time")

                if not (title_el and company_el and link_el):
                    continue

                url = (link_el.get("href") or "").split("?")[0]
                if not url or url in seen:
                    continue
                seen.add(url)

                posted_at = None
                if time_el and time_el.get("datetime"):
                    try:
                        posted_at = datetime.fromisoformat(time_el["datetime"])
                    except ValueError:
                        pass

                jobs.append(
                    RawJob(
                        title=title_el.get_text(strip=True),
                        company=company_el.get_text(strip=True),
                        location=(location_el.get_text(strip=True) if location_el else ""),
                        url=url,
                        posted_at=posted_at,
                    )
                )
            except Exception as e:
                logger.debug(f"LinkedIn card parse error: {e}")
                continue

        return jobs
