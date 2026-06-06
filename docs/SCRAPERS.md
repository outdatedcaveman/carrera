# Writing a Custom Scraper

Carrera's scrapers are small — most are 70–120 lines. If a job board you care about isn't supported, adding it is an afternoon's work.

## Contract

Every scraper inherits from `BaseScraper` (`backend/app/scrapers/base.py`) and implements one async method:

```python
class BaseScraper:
    source_type: ClassVar[str]                 # e.g. "linkedin"

    def __init__(self, source: Source, profile: SearchProfile): ...

    async def fetch(self) -> list[RawJob]: ...    # the only method you write
```

`RawJob` is a dataclass:

```python
@dataclass
class RawJob:
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None        # "BRL", "USD", …
    remote: bool | None = None
    seniority: str | None = None       # "junior" | "mid" | "senior" | "director" | …
    employment_type: str | None = None # "full-time" | "contract" | …
    posted_at: datetime | None = None
```

Only `title`, `company`, `url` are strictly required. Fill in as much as you can; the scorer and UI both degrade gracefully if fields are missing.

You don't dedupe, you don't score, you don't write to the DB. The engine does all of that — you just return a list.

## Minimum viable scraper

Here's a complete scraper for a hypothetical JSON API:

```python
# backend/app/scrapers/myboard.py
import logging
from .base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

class MyBoardScraper(BaseScraper):
    source_type = "myboard"

    async def fetch(self) -> list[RawJob]:
        query = self.config.get("query", "")
        location = self.config.get("location", "")

        try:
            resp = await self._get(
                "https://api.myboard.com/v1/search",
                params={"q": query, "location": location, "limit": self.max_jobs},
            )
            items = resp.json().get("results", [])
        except Exception as e:
            logger.warning(f"MyBoard fetch failed: {e}")
            return []

        jobs: list[RawJob] = []
        for it in items:
            jobs.append(RawJob(
                title=it["title"],
                company=it["company_name"],
                location=it.get("location", ""),
                url=it["url"],
                description=it.get("description", ""),
                remote=it.get("is_remote"),
                posted_at=None,   # parse to datetime if available
            ))
        return jobs
```

## Wiring it up

Three changes:

1. **Register in `base.py`**:
   ```python
   # backend/app/scrapers/base.py
   from .myboard import MyBoardScraper

   SCRAPER_REGISTRY = {
       "linkedin": LinkedInScraper,
       # ...
       "myboard": MyBoardScraper,          # ← add
   }
   ```
2. **Add to the frontend type list**:
   ```typescript
   // frontend/src/pages/Sources.tsx
   const SOURCE_TYPES = [
     // ...
     { value: 'myboard', label: 'MyBoard' },
   ]
   ```
3. **(Optional) Add PyInstaller hidden import**:
   ```python
   # carrera.spec
   hiddenimports = [
       # ...
       "app.scrapers.myboard",   # ← add
   ]
   ```

Now you can create a `myboard` source in the UI, drop a JSON config on it, and hit fetch.

## Useful helpers on `BaseScraper`

| Helper | What it does |
|---|---|
| `self._get(url, params=..., headers=...)` | HTTPX GET with UA rotation + rate-limit delay. Raises on non-2xx. |
| `self._post(url, json=...)` | Same, but POST. |
| `self._browser_session(impersonate="chrome124")` | Returns a **curl_cffi AsyncSession** that mimics Chrome's TLS + HTTP/2 fingerprint. Use this for hostile sources (Cloudflare-protected, fingerprint-checking). Supports cookies across requests via the session. |
| `self._browser_pause()` | Random 1–3s delay, same semantics as the `_get` sleep. Call before each browser request. |
| `self.config` | The `Source.config` JSON dict — your source-specific settings. |
| `self.profile.config` | The `SearchProfileConfig` dict — global search prefs. |
| `self.max_jobs` | Max rows the engine wants (respects `MAX_JOBS_PER_RUN`). |

### Signalling a block vs a miss

Raise `ScraperBlockedError` (from `.base`) when the target actively refuses the request — Cloudflare captcha, 403, LinkedIn's empty `<!DOCTYPE html>\n<!---->` stub. The scheduler turns that into a visible `last_error` on the source card in the UI. **Don't** raise it for parser misses (HTML changed) or empty-results queries — those should just return `[]`.

```python
from .base import BaseScraper, RawJob, ScraperBlockedError

async with self._browser_session() as s:
    await self._browser_pause()
    resp = await s.get(url, headers=MY_HEADERS)
    if _looks_like_block(resp.text):
        raise ScraperBlockedError("SomeSite served a challenge page.")
```

## Conventions

- **Fail quiet, log loud.** Wrap the outer HTTP call in `try / except` and return `[]` on failure. `logger.warning(...)` with enough context to debug later.
- **Short-circuit paging loops** when a page returns zero items — don't keep hitting empty pages.
- **Don't return more than `self.max_jobs * 3`** even after filtering. The engine trims anyway, but you'd be burning rate budget.
- **Normalize location strings.** If the API gives you city + state + country as separate fields, join them `", "` so the UI renders consistently.
- **Use descriptive config keys.** `{"search_query": "portfolio manager", "city": "São Paulo"}` is better than `{"q": "pm", "c": "SP"}`.

## Testing locally

The fastest loop:

```bash
# Backend running in one terminal.
curl -X POST http://localhost:8000/api/sources/<id>/fetch
# Tail the logs — you'll see each request + the final "fetched N jobs" line.
```

Once it's happy, toggle the source's `enabled=true` in the UI so the cron picks it up.

## Rate limits & politeness

Every scraper inherits the random 1–3s delay on `_get()`. If a board is strict:
- Lower `MAX_JOBS_PER_RUN` in `.env`.
- Bump `REQUEST_DELAY_MIN` / `REQUEST_DELAY_MAX`.
- Don't scrape on every cron — set the source's cron to `0 9 * * *` (once a day) via `scrape_schedule`.

If you're hitting an official API with an API key, add the key to `.env`, expose it via `app.config.Settings`, read it in your scraper. Don't hard-code.

## Defeating anti-bot (Indeed, LinkedIn)

Two sources — Indeed and LinkedIn — actively fight scrapers. Carrera handles them with a browser-impersonation client (`curl_cffi`, which speaks Chrome's TLS and HTTP/2 fingerprint) instead of plain `httpx`.

### How it works

- **Indeed** sits behind Cloudflare. Plain httpx gets `HTTP 403 — Blocked - Indeed.com`. `curl_cffi` with `impersonate="chrome124"` + a homepage warmup returns real results.
- **LinkedIn** killed its guest JSON endpoint (it returns a 26-byte empty stub now). Carrera fetches the public `/jobs/search/` HTML page instead, which still renders 50–60 job cards per request via curl_cffi.

Both scrapers raise `ScraperBlockedError` if the block gets through anyway, so you'll see a red error on the Sources card instead of a silent zero-jobs run.

### Optional: authenticated LinkedIn (power users)

LinkedIn's public HTML path works without an account, but it's noisier and missing richer fields (company size, seniority metadata, full description). If you want the authenticated path:

1. Log into linkedin.com in your browser.
2. Open DevTools → Application → Cookies → `linkedin.com`.
3. Copy the value of the `li_at` cookie.
4. Edit your LinkedIn source config (via PATCH `/api/sources/<id>`):
   ```json
   {
     "config": {
       "search_query": "...",
       "location": "Brazil",
       "filters": {"experience_level": ["mid-senior", "director"]},
       "session_cookie": "<paste li_at value here>"
     }
   }
   ```
5. The scraper will include the cookie on each request.

**This violates LinkedIn's Terms of Service.** Scraping with a logged-in session risks account warnings → checkpoints → permanent ban, especially at high request rates. Most practitioners use a burner account. Consider yourself warned — Carrera doesn't need the feature to work.
