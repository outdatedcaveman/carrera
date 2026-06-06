"""Generic RSS/Atom feed scraper."""
import logging
import feedparser
from datetime import datetime
from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)


class GenericRSSScraper(BaseScraper):
    source_type = "rss"

    async def fetch(self) -> list[RawJob]:
        feed_url = self.config.get("url", "")
        if not feed_url:
            logger.error("RSS scraper: no URL configured")
            return []

        try:
            resp = await self._get(feed_url)
            feed = feedparser.parse(resp.text)
        except Exception as e:
            logger.warning(f"RSS fetch error for {feed_url}: {e}")
            return []

        jobs = []
        for entry in feed.entries[: self.max_jobs]:
            try:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                jobs.append(
                    RawJob(
                        title=entry.get("title", ""),
                        company=entry.get("author", "") or self.config.get("default_company", ""),
                        location=self.config.get("default_location", "Remote"),
                        url=entry.get("link", ""),
                        description=entry.get("summary", ""),
                        posted_at=published,
                        remote=self.config.get("default_remote", None),
                    )
                )
            except Exception as e:
                logger.debug(f"RSS entry parse error: {e}")
                continue

        logger.info(f"RSS: fetched {len(jobs)} entries from {feed_url}")
        return jobs
