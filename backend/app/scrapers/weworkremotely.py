"""WeWorkRemotely scraper — uses their RSS feed."""
import logging
from datetime import datetime
import feedparser
from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

# Per-category RSS URLs often return empty to automated clients; main feed is reliable.
MAIN_FEED = "https://weworkremotely.com/remote-jobs.rss"

CATEGORY_FEEDS = {
    "business-management": MAIN_FEED,
    "executive": MAIN_FEED,
    "all": MAIN_FEED,
}


class WeWorkRemotelyScraper(BaseScraper):
    source_type = "weworkremotely"

    async def fetch(self) -> list[RawJob]:
        category = self.config.get("category", "business-management")
        feed_url = CATEGORY_FEEDS.get(category, MAIN_FEED)

        try:
            resp = await self._get(feed_url)
            feed = feedparser.parse(resp.text)
        except Exception as e:
            logger.warning(f"WeWorkRemotely fetch error: {e}")
            return []

        if not getattr(feed, "entries", None):
            try:
                resp = await self._get(MAIN_FEED)
                feed = feedparser.parse(resp.text)
                logger.info("WeWorkRemotely: feed empty, retried main remote-jobs.rss")
            except Exception as e2:
                logger.warning(f"WeWorkRemotely fallback error: {e2}")
                return []

        jobs = []
        for entry in feed.entries[: self.max_jobs]:
            try:
                title = entry.get("title", "")
                # Title format: "Company Name: Job Title"
                company, _, job_title = title.partition(": ")
                if not job_title:
                    job_title = title
                    company = ""

                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                jobs.append(
                    RawJob(
                        title=job_title.strip(),
                        company=company.strip(),
                        location="Remote",
                        url=entry.get("link", ""),
                        description=entry.get("summary", ""),
                        remote=True,
                        currency="USD",
                        posted_at=published,
                    )
                )
            except Exception as e:
                logger.debug(f"WeWorkRemotely entry parse error: {e}")
                continue

        logger.info(f"WeWorkRemotely: fetched {len(jobs)} jobs from category '{category}'")
        return jobs
