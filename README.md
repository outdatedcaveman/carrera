<p align="center">
  <img src="assets/logo.svg" alt="Carrera" width="360" />
</p>

<p align="center">
  <strong>Self-hosted job search, in motion.</strong><br>
  A desktop app that scrapes job boards, scores postings against your profile, and tailors your CV + cover letter for every application.
</p>

<p align="center">
  <a href="docs/GETTING_STARTED.md">Getting started</a> ·
  <a href="docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="docs/TAILORING.md">Tailoring</a> ·
  <a href="docs/SCRAPERS.md">Scrapers</a> ·
  <a href="docs/PACKAGING.md">Packaging</a> ·
  <a href="docs/BRANDING.md">Branding</a>
</p>

---

## What it does

- 🔎 **Scrape** LinkedIn, Gupy (BR), Indeed Brasil, RemoteOK, WeWorkRemotely, and arbitrary RSS feeds on a schedule or on demand.
- 🎯 **Score** each posting against your profile — title match, location, salary, skills, seniority — with weights you control.
- ✍️ **Tailor** your CV and draft a cover letter for a specific role using a free template engine, a local Ollama model, or the OpenAI / Anthropic API (with cost estimated up front).
- 📄 **Export** polished PDFs of the tailored CV and cover letter.
- 📋 **Track** applications on a Kanban board: Discovered → Saved → Applied → Interview → Offer.
- 📊 **Dashboard** — jobs over time, category breakdown, top hiring companies.

Everything runs on your machine. Your CV and search data never leave your computer, except for outbound scraper requests and (optionally) AI API calls you approve.

## Install & run

Three ways, pick one:

### 1. Desktop app (Windows)

```powershell
# Build once
cd frontend ; npm install ; npm run build ; cd ..
pyinstaller carrera.spec --noconfirm

# Put a shortcut on your desktop
powershell -ExecutionPolicy Bypass -File scripts\install-shortcut.ps1

# Double-click the Carrera icon on your desktop.
```

The exe lives at `dist\Carrera\Carrera.exe`. Data in `%USERPROFILE%\.carrera\`.

### 2. Docker

```bash
git clone https://github.com/<you>/carrera.git
cd carrera
cp .env.example .env
cd frontend && npm install && npm run build && cd ..
docker compose up --build
# → http://localhost:3000
```

### 3. Development (hot reload)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (another terminal)
cd frontend
npm install
npm run dev   # → http://localhost:5173
```

## First 15 minutes

1. Open the app. The Dashboard shows a **Welcome to Carrera** panel with a 3-step checklist.
2. Go to **Sources** — the five default sources are pre-seeded. Enable the ones you want, tweak `search_query` / `location` in their config.
3. Click **Fetch All** at the top right. Keep the tab open while it runs (few minutes).
4. Head to **Jobs**. Every posting has a score 0-100 and a category badge (strong match / good / worth-a-look / reach).
5. Open a job → **Tailor Resume** → pick a provider (template is free and instant; Ollama if you have it; OpenAI/Anthropic for highest quality) → download the PDFs.

Full walkthrough: **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**.

## Configuration

All settings live in `.env` (see `.env.example`). Most useful:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/carrera.db` | SQLite file path |
| `SCRAPE_SCHEDULE` | `0 8,18 * * *` | Cron for auto-scraping (8am + 6pm) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local LLM endpoint |
| `OLLAMA_MODEL` | `llama3` | Which Ollama model to use |
| `OPENAI_API_KEY` | _blank_ | Enables OpenAI tailoring |
| `ANTHROPIC_API_KEY` | _blank_ | Enables Anthropic tailoring |
| `PDF_OUTPUT_DIR` | `./data/pdfs` | Where tailored PDFs are written |
| `REQUEST_DELAY_MIN` / `MAX` | `1.0` / `3.0` | Rate-limit floor/ceiling for scrapers |

No API keys? Carrera still works end-to-end — the **template** tailoring provider is pure Python and free.

## Repo layout

```
carrera/
├── assets/             # logo, icon.ico, brand PNGs
├── backend/
│   └── app/            # FastAPI: api/, engine/, scrapers/, data/seed.py
├── docs/               # GETTING_STARTED, ARCHITECTURE, TAILORING, SCRAPERS, PACKAGING, BRANDING
├── frontend/
│   └── src/            # React + Vite + Tailwind + TanStack Query
├── scripts/            # install-shortcut.ps1
├── carrera.spec        # PyInstaller spec → Windows .exe
├── launcher.py         # desktop entrypoint (uvicorn + pywebview)
└── docker-compose.yml  # headless server deployment
```

Architecture diagram + data model: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## The name

**Carrera** — Portuguese/Spanish for "career". And also, pleasingly, for "race". Short, memorable, moves forward. Pronounced *cah-RARE-uh*.

## License

MIT. Use it, fork it, ship it. If you improve a scraper or add a provider, a PR is appreciated.
