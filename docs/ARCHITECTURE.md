# Architecture

A one-page tour of how Carrera is put together. Keep this file updated when you refactor.

## Runtime topology

```
            ┌──────────────────────────────────────────┐
            │             Carrera.exe                   │
            │                                           │
            │  ┌─────────────┐      ┌───────────────┐  │
            │  │  launcher   │──▶──▶│  pywebview    │  │
            │  │  (main thd) │      │  (Edge WV2)   │  │
            │  └─────┬───────┘      └───────┬───────┘  │
            │        │                      │          │
            │        ▼ threading            ▼ http     │
            │  ┌─────────────────────────────────────┐ │
            │  │  uvicorn — FastAPI on 127.0.0.1:18432│ │
            │  │   ├ /api/jobs, /sources, /profiles   │ │
            │  │   ├ /api/dashboard, /resumes         │ │
            │  │   ├ /api/tailoring                   │ │
            │  │   └ /            (React static)      │ │
            │  └───────────┬─────────────────────────┘ │
            │              │                           │
            │              ▼                           │
            │     ┌────────────────┐                   │
            │     │ SQLite (WAL)   │   ~/.carrera/     │
            │     │ + APScheduler  │                   │
            │     │ + scrapers     │────http──▶ job    │
            │     └────────────────┘              boards │
            └──────────────────────────────────────────┘
```

When running in Docker the picture is the same minus pywebview — `uvicorn` is the entrypoint and the React bundle is served off the FastAPI app.

## Backend

**FastAPI + SQLAlchemy 2.0 + Pydantic v2.** All DB access goes through the `Session` dependency (`app.database.get_db`). Long-running work that can't hold a request — scraping and tailoring — opens its own `SessionLocal` to avoid the request lifecycle.

```
backend/app/
├── main.py               # FastAPI app factory, lifespan, static mount
├── config.py             # Settings (pydantic-settings, reads .env)
├── database.py           # engine, SessionLocal, init_db with WAL pragmas
├── models.py             # 8 tables — see Data model below
├── schemas.py            # Pydantic DTOs
├── api/                  # routers (jobs, sources, profiles, dashboard, resumes, tailoring)
├── engine/
│   ├── scheduler.py      # APScheduler cron jobs + run_source_now
│   ├── scorer.py         # weighted scoring → JobScore rows
│   ├── dedup.py          # url_hash-based deduplication
│   ├── tailoring_engine.py   # 4 providers: template, ollama, openai, anthropic
│   └── pdf_generator.py  # ReportLab resume + cover letter
├── scrapers/
│   ├── base.py           # BaseScraper + RawJob dataclass + get_scraper() registry
│   ├── linkedin.py, indeed.py, gupy.py, remoteok.py, weworkremotely.py, generic_rss.py
└── data/
    ├── resume_en.json, resume_pt.json       # seed CV data
    └── seed.py           # idempotent seeding on app start
```

### Scheduler lifecycle

`start_scheduler()` runs during FastAPI's `lifespan` enter. It registers one cron job per enabled `Source` using `SCRAPE_SCHEDULE`. The scheduler uses `AsyncIOScheduler` — so it shares the uvicorn event loop, no extra threads.

`run_source_now(source_id)` is the same function the cron fires, exposed over `/api/sources/{id}/fetch` and `/api/sources/fetch-all`. It:
1. Loads the source and its profile.
2. Calls the scraper's `fetch()` → `list[RawJob]`.
3. Deduplicates on `url_hash`.
4. Scores each job via `scorer.score_job()`.
5. Writes `Job` + `JobScore` rows.
6. Updates source metrics (`last_fetched`, `jobs_found_total`, `last_error`).

### Tailoring pipeline

`tailoring_engine.tailor_resume()` is a single dispatch. The provider enum (`template | ollama | openai | anthropic`) selects an implementation that all return the same shape:

```python
TailoredOutput(
    resume_data: CVData,
    cover_letter: str,
    model_used: str,
    cost_usd: float,
    notes: dict,
)
```

- **template** — pure Python. Re-ranks bullets by keyword overlap with the JD, rewrites summary from a template, uses a cover-letter `ApplicationTemplate` row.
- **ollama** — POST to `http://localhost:11434/api/generate`. Zero cost.
- **openai / anthropic** — direct HTTPX calls (no SDK). Cost estimated up front from per-model pricing in `_COST_PER_1K_TOKENS`, shown in the UI before the call fires.

Output is persisted as a `TailoredApplication` row with the generated CV JSON, cover letter text, and PDF paths (written to `PDF_OUTPUT_DIR`).

## Data model

8 tables. Only the interesting relationships:

```
SearchProfile ──┐
                ├─▶ Source (config JSON, schedule inherited)
                │
                ▼
              Job (url_hash UNIQUE)
                │
                ├─▶ JobScore (1-to-many, one row per dimension)
                └─▶ ActivityLog (status changes, notes)

BaseResume ──▶ TailoredApplication ◀── Job
                                   │
                                   └─▶ ApplicationTemplate (cover-letter shell)
```

- `Job.url_hash` is a SHA-256 of the canonical URL; `UNIQUE` prevents dupes across re-scrapes and across sources.
- `Job.score_details` is the 1-to-many JobScore → exposed in the UI's score breakdown tooltip.
- `TailoredApplication.tailored_resume_data` is the full `CVData` JSON; this means old tailored versions survive CV edits.

## Frontend

**Vite + React 18 + TypeScript (strict) + TanStack Query + Tailwind.** No global state — TanStack Query cache *is* the state.

```
frontend/src/
├── main.tsx, App.tsx   # React entry + router
├── api/                # typed client per resource (jobs, sources, resumes, …)
├── components/         # reusable (Navbar, JobCard, JobDetail, KanbanBoard, TailoringWorkflow, …)
├── pages/              # one per route (Dashboard, Jobs, Pipeline, Sources, Settings, ResumeEditor)
├── types/index.ts      # mirrors backend schemas.py
└── lib/dateUtils.ts    # parseApiUtc — handles naive UTC from the Python side
```

Query keys are simple arrays: `['jobs']`, `['sources']`, `['stats']`, `['jobs-over-time']`. Mutations invalidate the keys they affect (see `invalidateSourcesAndJobs` in Sources.tsx for the cross-resource case).

## Packaging

`carrera.spec` (PyInstaller) bundles the backend + `frontend/dist` + pywebview assets into `dist/Carrera/Carrera.exe`. `launcher.py` is the entrypoint — it sets up paths (`sys._MEIPASS` when frozen), migrates a legacy `.careerops/` dir if present, starts uvicorn on a background thread, and opens a pywebview window.

The Windows shortcut installer (`scripts/install-shortcut.ps1`) creates a `.lnk` with the correct icon on the user's desktop.

## Cross-cutting concerns

- **Timezones.** SQLite stores naive datetimes in UTC. The backend writes them that way; the frontend wraps every parse in `parseApiUtc()` to avoid local-wall-time drift.
- **Logging.** stdlib logging, level `INFO`. Scrapers warn-log API errors but never raise — a broken source doesn't kill a fetch run.
- **Rate limiting.** `BaseScraper._get()` applies a random delay between `REQUEST_DELAY_MIN` and `REQUEST_DELAY_MAX`, default 1–3s. Tune these in `.env`.
- **Secrets.** Never committed. `.env.example` enumerates every key Carrera reads; anything else is a bug.
