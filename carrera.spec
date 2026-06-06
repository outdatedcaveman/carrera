# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Carrera desktop app.
Run from the project root:  pyinstaller carrera.spec --noconfirm
"""
import sys, os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)
SITE = Path(sys.executable).parent / "Lib" / "site-packages"

# ── Collect data ───────────────────────────────────────────────────────────────
datas = [
    # Frontend build (served as static files)
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    # CV seed JSONs
    (str(ROOT / "backend" / "app" / "data"), "backend/app/data"),
    # pywebview assets (HTML templates, js)
    *collect_data_files("webview"),
    # APScheduler timezone data
    *collect_data_files("apscheduler"),
    # tzdata / tzlocal
    *collect_data_files("tzdata", include_py_files=True),
    # curl_cffi ships libcurl-impersonate DLLs + certs as package data;
    # PyInstaller's default analysis misses them.
    *collect_data_files("curl_cffi", include_py_files=True),
    # playwright bundles a node driver + browser-launcher scripts; without
    # these the autofill engine errors out at sync_playwright().
    *collect_data_files("playwright", include_py_files=True),
]

# ── Hidden imports (dynamic imports PyInstaller can't auto-detect) ─────────────
hiddenimports = [
    # FastAPI / Starlette internals
    "fastapi",
    "fastapi.middleware.cors",
    "starlette.staticfiles",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.base",
    "anyio",
    "anyio.from_thread",
    "anyio._backends._asyncio",
    "sniffio",
    # Uvicorn
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # SQLAlchemy dialects
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    # Pydantic
    "pydantic",
    "pydantic_settings",
    # APScheduler
    "apscheduler",
    "apscheduler.schedulers.asyncio",
    "apscheduler.triggers.cron",
    "apscheduler.executors.asyncio",
    "apscheduler.jobstores.memory",
    # pywebview
    "webview",
    "webview.platforms.winforms",
    "clr",
    # BeautifulSoup
    "bs4",
    "lxml",
    "lxml.etree",
    "lxml._elementpath",
    # feedparser
    "feedparser",
    "sgmllib3k",
    # Other
    "fuzzywuzzy",
    "Levenshtein",
    "reportlab",
    "reportlab.lib",
    "reportlab.platypus",
    "reportlab.pdfbase",
    # pypdf (CV PDF import)
    "pypdf",
    "pypdf.generic",
    "pypdf._cmap",
    "pypdf._encryption",
    "httpx",
    # curl_cffi (browser-impersonation client for Indeed/LinkedIn)
    "curl_cffi",
    "curl_cffi.requests",
    "curl_cffi.requests.session",
    "curl_cffi.curl",
    "curl_cffi.aio",
    # playwright (autofill driver — uses system Chrome, no Chromium download)
    "playwright",
    "playwright.sync_api",
    "playwright._impl._driver",
    "pyee",
    "greenlet",
    "aiofiles",
    "multipart",
    "dotenv",
    "jinja2",
    "PIL",
    "tenacity",
    # Our app modules
    "app",
    "app.main",
    "app.config",
    "app.database",
    "app.models",
    "app.schemas",
    "app.api.jobs",
    "app.api.sources",
    "app.api.profiles",
    "app.api.dashboard",
    "app.api.resumes",
    "app.api.tailoring",
    "app.api.app_settings",
    "app.api.quick_answers",
    "app.api.autofill",
    "app.scrapers.base",
    "app.scrapers.linkedin",
    "app.scrapers.indeed",
    "app.scrapers.gupy",
    "app.scrapers.generic_rss",
    "app.scrapers.remoteok",
    "app.scrapers.weworkremotely",
    "app.engine.scheduler",
    "app.engine.scorer",
    "app.engine.dedup",
    "app.engine.tailoring_engine",
    "app.engine.pdf_generator",
    "app.engine.cv_importer",
    "app.engine.settings_store",
    "app.engine.autofill",
    "app.data.seed",
]

# ── Analysis ───────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT), str(ROOT / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "test", "tests", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Carrera",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(ROOT / "assets" / "icon.ico") if (ROOT / "assets" / "icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Carrera",
)
