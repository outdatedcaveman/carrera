"""Indeed Brasil scraper.

Indeed sits behind Cloudflare, which blocks plain httpx with HTTP 403 and a
"Blocked - Indeed.com" page. We fetch via curl_cffi's Chrome TLS/HTTP2
impersonation, warm cookies by hitting the homepage first, and still
surface a ScraperBlockedError if the challenge gets through.
"""
import logging
import re
from bs4 import BeautifulSoup
from .base import BaseScraper, RawJob, ScraperBlockedError

logger = logging.getLogger(__name__)


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
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


def _is_block_page(html: str) -> bool:
    """Detect Indeed/Cloudflare bot challenge pages.

    A genuine results page contains many `data-jk="..."` anchors. We detect
    blocks by title and challenge markers, but the authoritative signal is
    "no data-jk anchors on a first-page fetch".
    """
    if not html:
        return True
    head = html[:4096].lower()
    if "<title>blocked - indeed" in head:
        return True
    if "captcha-delivery.com" in head or "cf_chl_opt" in head:
        return True
    if "cloudflare" in head and ("attention required" in head or "checking your browser" in head):
        return True
    return False


class IndeedScraper(BaseScraper):
    source_type = "indeed"

    HOME_URL = "https://br.indeed.com/"
    BASE_URL = "https://br.indeed.com/jobs"

    async def fetch(self) -> list[RawJob]:
        query = (self.config.get("query") or self.config.get("search_query") or "").strip()
        location = (self.config.get("location") or "São Paulo, SP").strip()

        params: dict = {"q": query or " ", "l": location, "start": 0}

        jobs: list[RawJob] = []
        first_page_empty = False

        async with self._browser_session() as session:
            # Warm up cookies by hitting the homepage first
            try:
                await self._browser_pause()
                await session.get(self.HOME_URL, headers=BROWSER_HEADERS)
            except Exception as e:
                logger.debug(f"Indeed warmup failed (non-fatal): {e}")

            for start in range(0, min(self.max_jobs, 100), 10):
                params["start"] = start
                try:
                    await self._browser_pause()
                    resp = await session.get(self.BASE_URL, params=params, headers=BROWSER_HEADERS)
                except Exception as e:
                    logger.warning(f"Indeed fetch error at start={start}: {e}")
                    break

                status = getattr(resp, "status_code", None)
                text = getattr(resp, "text", "") or ""

                if status == 403 and start == 0:
                    raise ScraperBlockedError(
                        "Indeed returned HTTP 403 even through the browser-impersonation "
                        "client. The Cloudflare challenge was not passed — try again later, "
                        "or Indeed is blocking this IP range."
                    )

                if _is_block_page(text) and start == 0:
                    raise ScraperBlockedError(
                        "Indeed served a block/challenge page instead of search results."
                    )

                page_jobs = self._parse(text)
                if not page_jobs:
                    if start == 0:
                        first_page_empty = True
                    break
                jobs.extend(page_jobs)
                if len(jobs) >= self.max_jobs:
                    break

        if first_page_empty and not jobs:
            # Got HTTP 200 with no `data-jk` anchors: most likely a soft block
            # (Indeed sometimes serves a stripped page to flagged fingerprints).
            raise ScraperBlockedError(
                "Indeed returned HTTP 200 but the page had no job anchors — "
                "likely a soft bot-block. Refreshed browser impersonation or a "
                "different IP may help."
            )

        logger.info(f"Indeed: fetched {len(jobs)} jobs for query='{query}'")
        return jobs[: self.max_jobs]

    def _parse(self, html: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "lxml")
        jobs: list[RawJob] = []
        seen: set[str] = set()

        # Modern Indeed: job links carry data-jk on <a>
        anchors = soup.select("a[data-jk]")
        for a in anchors:
            jk = (a.get("data-jk") or "").strip()
            if not jk or len(jk) < 8 or jk in seen:
                continue
            seen.add(jk)

            # Prefer the inner <span> (the rendered title); fall back to aria-label.
            inner = a.select_one("span.jcs-JobTitle, span[id^='jobTitle'], span")
            title = inner.get_text(strip=True) if inner else ""
            if not title:
                title = (a.get("aria-label") or "").strip()
            # Indeed's aria-label is "informações completas da vaga de <TITLE>" /
            # "full job details for <TITLE>" — strip the prefix if present.
            title = re.sub(
                r"^(informa[cç][oõ]es completas da vaga de|full job details for)\s+",
                "",
                title,
                flags=re.IGNORECASE,
            )
            if not title:
                continue

            container = a.find_parent("td", class_=re.compile(r"result", re.I))
            if not container:
                container = a.find_parent("div", class_=re.compile(r"job|card|slider|mosaic|result", re.I))
            for _ in range(10):
                if container is None:
                    break
                if container.select_one('[data-testid="company-name"]'):
                    break
                container = container.parent

            company_el = None
            location_el = None
            salary_el = None
            if container:
                company_el = container.select_one('[data-testid="company-name"]') or container.select_one(
                    "span[class*='companyName']"
                )
                location_el = container.select_one('[data-testid="text-location"]') or container.select_one(
                    "div[class*='companyLocation']"
                )
                salary_el = container.select_one('[data-testid="attribute_snippet_testid"]')

            company = company_el.get_text(strip=True) if company_el else "—"
            location = location_el.get_text(strip=True) if location_el else ""
            salary_text = salary_el.get_text(strip=True) if salary_el else ""
            sal_min, sal_max = self._parse_salary(salary_text)

            try:
                jobs.append(
                    RawJob(
                        title=title[:512],
                        company=company[:512],
                        location=location[:512],
                        url=f"https://br.indeed.com/viewjob?jk={jk}",
                        salary_min=sal_min,
                        salary_max=sal_max,
                        currency="BRL",
                    )
                )
            except Exception as e:
                logger.debug(f"Indeed row build error: {e}")

        if jobs:
            return jobs

        # Legacy structure: any node with data-jk (mosaic tiles)
        for card in soup.select("[data-jk]"):
            try:
                job_key = (card.get("data-jk") or "").strip()
                if not job_key or len(job_key) < 8 or job_key in seen:
                    continue
                seen.add(job_key)
                title_el = card.select_one("[class*='jobTitle']") or card.select_one("h2 span") or card.select_one(
                    "h2"
                )
                company_el = card.select_one("[data-testid='company-name']") or card.select_one(".companyName")
                location_el = card.select_one("[data-testid='text-location']") or card.select_one(".companyLocation")
                salary_el = card.select_one("[data-testid='attribute_snippet_testid']")

                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title:
                    continue
                company = company_el.get_text(strip=True) if company_el else "—"

                salary_text = salary_el.get_text(strip=True) if salary_el else ""
                sal_min, sal_max = self._parse_salary(salary_text)

                jobs.append(
                    RawJob(
                        title=title[:512],
                        company=company[:512],
                        location=(location_el.get_text(strip=True) if location_el else "")[:512],
                        url=f"https://br.indeed.com/viewjob?jk={job_key}",
                        salary_min=sal_min,
                        salary_max=sal_max,
                        currency="BRL",
                    )
                )
            except Exception as e:
                logger.debug(f"Indeed card parse error: {e}")
                continue

        return jobs

    def _parse_salary(self, text: str) -> tuple[float | None, float | None]:
        if not text:
            return None, None
        nums = re.findall(r"[\d.,]+", text.replace(".", "").replace(",", ""))
        floats = []
        for n in nums:
            try:
                floats.append(float(n))
            except ValueError:
                pass
        if len(floats) == 0:
            return None, None
        if len(floats) == 1:
            return floats[0], None
        return floats[0], floats[1]
