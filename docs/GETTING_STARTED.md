# Getting Started with Carrera

This guide walks you from a fresh install to a tailored PDF application in about 20 minutes.

## What Carrera does

Carrera is a self-hosted job-search engine. It:

1. **Scrapes** job boards (LinkedIn, Gupy, Indeed Brasil, RemoteOK, WeWorkRemotely, arbitrary RSS) on a schedule or on demand.
2. **Scores** every posting against your profile — title match, location, salary, skills, seniority — using weights you control.
3. **Tailors your CV** to a specific posting (via a rule-based template engine, a local Ollama model, or an optional OpenAI/Anthropic call) and drafts a cover letter.
4. **Tracks your pipeline** on a Kanban board: Discovered → Saved → Applied → Interview → Offer.

Everything runs locally. Your CV, your applied-to companies, your notes — nothing leaves your machine except the outbound scraper requests and (optionally) your AI API calls.

---

## Running Carrera

There are three supported ways to run it. Pick the one that matches how you got it.

### A. The desktop app (recommended for daily use)

If you downloaded a release or ran `pyinstaller carrera.spec`:

1. Double-click `Carrera.exe` (Windows) — or the platform equivalent.
2. A native window opens on `http://127.0.0.1:18432`. No browser tabs.
3. Data lives in `~/.carrera/` (Windows: `C:\Users\<you>\.carrera`).

To put Carrera one click away, run `scripts/install-shortcut.ps1` from PowerShell — it drops a desktop shortcut with the Carrera icon.

### B. Docker (recommended for a headless server)

```bash
git clone https://github.com/<you>/carrera.git
cd carrera
cp .env.example .env      # edit as needed
cd frontend && npm install && npm run build && cd ..
docker compose up --build
```

Open http://localhost:3000.

### C. Development (backend + Vite dev server)

```bash
# Terminal 1 — backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data/pdfs
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev     # http://localhost:5173, proxies /api to :8000
```

---

## The 15-minute first run

### Step 1 — Check your base CV (2 min)

Open **Resume** in the sidebar. Carrera's seed script pre-populates a default English and Portuguese CV. If that's not you:

- Fill in personal info, summary, experience bullets, skills on each tab.
- Click **Preview** to see how it'll render in PDF.
- Click **Save** after edits.

**Why this matters:** when you tailor to a job, Carrera pulls bullets and phrasing from *this* CV. The better the raw material, the better the tailored output.

### Step 2 — Configure your sources (3 min)

Open **Sources**. Five sources are seeded by default:

| Source | What it scrapes | Config you'll tweak |
|---|---|---|
| LinkedIn | `jobs-guest/search` endpoint | `search_query`, `location`, `filters.experience_level` |
| Gupy | Portal JSON API | `search_query`, `city`, `state` |
| Indeed Brasil | HTML search page | `query`, `location` |
| RemoteOK | JSON API | `tags` (comma-separated) |
| WeWorkRemotely | RSS feed | `category` |

For each one: click the source, edit its JSON config to match your target roles, enable it.

> **Gotcha**: Gupy's `state` filter wants the full name ("São Paulo"), not the UF ("SP"). Carrera auto-normalizes this, but if you paste a custom city/state into another field, use full names.

### Step 3 — Fetch (5 min)

Click **Fetch All** at the top-right of the Sources page. It hits each enabled source sequentially. **Keep the tab open while it runs** — the request is long-polling and cancelling the page cancels the job.

Expect 100–300 jobs on a first run. Watch the "jobs ever ingested" counter tick up.

### Step 4 — Triage (3 min)

Open **Jobs**. Every posting has a score (0–100) and category:

- **Strong match** (green) — probable good fit
- **Good match** (blue) — worth reviewing
- **Worth a look** (amber) — might be interesting
- **Reach** (grey) — stretch or poor match

Click a job to expand it. Use the status dropdown to move promising ones to **Saved**. Trashed jobs go to the bottom — they don't clutter your pipeline.

### Step 5 — Tailor (5 min)

Inside a saved job, click **Tailor Resume**. You'll see:

1. **Analyze** — extracted required / preferred skills, detected language, your match score.
2. **Configure** — pick the base CV language, pick an AI provider (template is free; Ollama is local + free; OpenAI/Anthropic show a cost estimate before running), optionally check which of your experiences to emphasize, add custom instructions.
3. **Preview** — see the tailored CV + cover letter. Download both as PDFs.

Move the job to **Applied** once you've sent the application.

---

## Next steps

- **Schedule**: set `SCRAPE_SCHEDULE` in your `.env` to have Carrera auto-fetch (default: 8am and 6pm daily).
- **Tune scoring**: open **Settings** → edit `scoring_weights`. The defaults are 35% title / 20% location / 15% salary / 20% skills / 10% seniority.
- **Add a custom source**: see [SCRAPERS.md](SCRAPERS.md) — it's ~30 lines of Python.
- **Turn off AI you don't need**: leave `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` blank if you only want template + Ollama.

## Troubleshooting

**The app won't start / port 18432 busy.**
Another Carrera instance is running. Kill it in Task Manager (look for `Carrera.exe` or `python.exe`) and relaunch.

**A source shows 0 jobs even after "Fetch All".**
Check the source's `last_error`. Most common: search query too narrow, or the site changed its HTML (Indeed does this regularly). Try broadening the query; file an issue if a scraper is broken.

**Ollama tailoring hangs.**
Make sure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull llama3`). Carrera defaults to `llama3`; change `OLLAMA_MODEL` in `.env` if you prefer another.

**"ai_cost_usd" looks high on a small job.**
The estimate includes the full job description token count. For a normal posting it's a few cents with `gpt-4o-mini` or `claude-haiku-4-5`. Template and Ollama are always $0.
