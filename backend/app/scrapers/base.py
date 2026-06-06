"""Base scraper interface. All source adapters must implement this."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import logging
import asyncio
import random
import httpx
from ..config import get_settings

try:
    # curl_cffi impersonates Chrome's TLS + HTTP/2 fingerprint, which defeats
    # most Cloudflare-style bot blocks that sniff at the TLS layer.
    # Shipped as part of the Carrera bundle; import-guarded so tests / dev
    # environments without it still run the other scrapers.
    from curl_cffi.requests import AsyncSession as _CurlAsyncSession  # type: ignore
    _HAS_CURL_CFFI = True
except Exception:  # pragma: no cover - only hit in minimal envs
    _CurlAsyncSession = None  # type: ignore
    _HAS_CURL_CFFI = False

logger = logging.getLogger(__name__)
settings = get_settings()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


class ScraperBlockedError(RuntimeError):
    """Raised when a source actively blocks the scraper (captcha / 403 / empty stub).

    Unlike a parser miss, this signals the target site is refusing us — the user
    should see it in the UI as `last_error` rather than a silent zero-jobs run.
    """
    pass


@dataclass
class RawJob:
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = "BRL"
    remote: bool | None = None
    seniority: str | None = None
    employment_type: str | None = None
    posted_at: datetime | None = None
    extra: dict = field(default_factory=dict)

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()[:64]


class BaseScraper(ABC):
    source_type: str = "unknown"

    def __init__(self, config: dict):
        self.config = config
        self.max_jobs = settings.max_jobs_per_run

    @abstractmethod
    async def fetch(self) -> list[RawJob]:
        """Fetch jobs from this source. Must be implemented by each adapter."""
        ...

    async def _get(self, url: str, **kwargs) -> httpx.Response:
        delay = random.uniform(settings.request_delay_min, settings.request_delay_max)
        await asyncio.sleep(delay)
        async with httpx.AsyncClient(headers=HEADERS, timeout=settings.request_timeout, follow_redirects=True) as client:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response

    async def _post(self, url: str, **kwargs) -> httpx.Response:
        delay = random.uniform(settings.request_delay_min, settings.request_delay_max)
        await asyncio.sleep(delay)
        async with httpx.AsyncClient(headers=HEADERS, timeout=settings.request_timeout, follow_redirects=True) as client:
            response = await client.post(url, **kwargs)
            response.raise_for_status()
            return response

    def _browser_session(self, impersonate: str = "chrome124"):
        """Return a curl_cffi AsyncSession with Chrome TLS/HTTP2 impersonation.

        Use via `async with self._browser_session() as s:` in scrapers that face
        hostile anti-bot (Indeed, LinkedIn). Callers are expected to send their
        own headers per-request and may optionally warm cookies by hitting the
        target site's homepage before the real call.
        """
        if not _HAS_CURL_CFFI:
            raise RuntimeError(
                "curl_cffi is not available. Install it with `pip install curl_cffi` "
                "or add it to requirements.txt for bundled builds."
            )
        return _CurlAsyncSession(impersonate=impersonate, timeout=settings.request_timeout)

    @staticmethod
    async def _browser_pause():
        """Randomized pacing delay, same semantics as _get's sleep."""
        delay = random.uniform(settings.request_delay_min, settings.request_delay_max)
        await asyncio.sleep(delay)


def get_scraper(source_type: str, config: dict) -> BaseScraper:
    from .linkedin import LinkedInScraper
    from .indeed import IndeedScraper
    from .gupy import GupyScraper
    from .generic_rss import GenericRSSScraper
    from .remoteok import RemoteOKScraper
    from .weworkremotely import WeWorkRemotelyScraper

    registry = {
        "linkedin": LinkedInScraper,
        "indeed": IndeedScraper,
        "gupy": GupyScraper,
        "rss": GenericRSSScraper,
        "remoteok": RemoteOKScraper,
        "weworkremotely": WeWorkRemotelyScraper,
    }

    cls = registry.get(source_type)
    if not cls:
        raise ValueError(f"Unknown source type: {source_type}")
    return cls(config)
