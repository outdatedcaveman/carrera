"""RemoteOK scraper — uses their public JSON API."""
import logging
from datetime import datetime
from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"


class RemoteOKScraper(BaseScraper):
    source_type = "remoteok"

    async def fetch(self) -> list[RawJob]:
        tags = self.config.get("tags", [])

        try:
            resp = await self._get(REMOTEOK_API, headers={"Accept": "application/json"})
            data = resp.json()
        except Exception as e:
            logger.warning(f"RemoteOK fetch error: {e}")
            return []

        # First item is metadata
        entries = data[1:] if len(data) > 1 else []

        jobs = []
        for item in entries[: self.max_jobs]:
            try:
                item_tags = [t.lower() for t in item.get("tags", [])]
                if tags and not any(t in item_tags for t in tags):
                    continue

                date_raw = item.get("date")
                posted_at = None
                if date_raw:
                    try:
                        posted_at = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                sal_min = item.get("salary_min")
                sal_max = item.get("salary_max")

                jobs.append(
                    RawJob(
                        title=item.get("position", ""),
                        company=item.get("company", ""),
                        location="Remote",
                        url=item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}",
                        description=item.get("description", ""),
                        salary_min=float(sal_min) if sal_min else None,
                        salary_max=float(sal_max) if sal_max else None,
                        currency="USD",
                        remote=True,
                        posted_at=posted_at,
                    )
                )
            except Exception as e:
                logger.debug(f"RemoteOK item parse error: {e}")
                continue

        logger.info(f"RemoteOK: fetched {len(jobs)} jobs")
        return jobs
