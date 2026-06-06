import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db, SessionLocal
from .engine.scheduler import start_scheduler, stop_scheduler
from .api import jobs, sources, profiles, dashboard, resumes, tailoring, app_settings, quick_answers, autofill
from .data.seed import run_all_seeds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Carrera starting up...")
    pdf_dir = settings.pdf_output_dir
    os.makedirs(pdf_dir, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        run_all_seeds(db)
    finally:
        db.close()
    start_scheduler()
    yield
    logger.info("Carrera shutting down...")
    stop_scheduler()


app = FastAPI(
    title="Carrera API",
    version="1.0.0",
    description="Job search automation with AI-powered resume tailoring",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(resumes.router, prefix="/api")
app.include_router(tailoring.router, prefix="/api")
app.include_router(app_settings.router, prefix="/api")
app.include_router(quick_answers.router, prefix="/api")
app.include_router(autofill.router, prefix="/api")

# Serve the React frontend build (production)
# Env var set by launcher.py when running as a frozen exe
# (legacy CAREEROPS_FRONTEND_DIST is honoured for one release)
_fe_env = os.environ.get("CARRERA_FRONTEND_DIST") or os.environ.get("CAREEROPS_FRONTEND_DIST")
if _fe_env:
    FRONTEND_BUILD = Path(_fe_env)
elif getattr(sys, "frozen", False):
    FRONTEND_BUILD = Path(sys._MEIPASS) / "frontend" / "dist"  # type: ignore[attr-defined]
else:
    FRONTEND_BUILD = Path(__file__).parent.parent.parent / "frontend" / "dist"

if FRONTEND_BUILD.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_BUILD), html=True), name="frontend")
    logger.info(f"Serving frontend from {FRONTEND_BUILD}")
