# Packaging Carrera as a Desktop Executable

Carrera ships as a single-folder Windows executable using PyInstaller + pywebview. This page is the recipe.

## Prerequisites

- Python 3.12 (the spec is pinned)
- Node 18+
- Windows 10/11 (pywebview uses Edge WebView2, preinstalled on 11; download for 10)

```powershell
# from repo root
python -m pip install --upgrade pip
python -m pip install pyinstaller pywebview
python -m pip install -r backend/requirements.txt
```

## Build

Two steps:

```powershell
# 1. Frontend bundle — PyInstaller copies this into the exe
cd frontend
npm install
npm run build           # emits frontend/dist/
cd ..

# 2. PyInstaller — reads carrera.spec
pyinstaller carrera.spec --noconfirm
```

Output lands in `dist/Carrera/` (~130 MB). The runnable entrypoint is `dist/Carrera/Carrera.exe`.

## What's in the bundle

`carrera.spec` tells PyInstaller:

- **Entry point**: `launcher.py` — starts uvicorn on a thread, opens pywebview on `127.0.0.1:18432`.
- **Data files**: `frontend/dist/` (static UI), `backend/app/data/` (CV seeds), apscheduler + tzdata timezone files, pywebview platform assets.
- **Hidden imports**: modules FastAPI/uvicorn/SQLAlchemy resolve dynamically that PyInstaller's static analysis misses — all listed explicitly in the spec.
- **Excludes**: `tkinter`, `unittest`, `pytest` — save ~20 MB.
- **Icon**: `assets/icon.ico` (generated from the Carrera mark).

## Runtime behaviour

When the user launches `Carrera.exe`:

1. PyInstaller's bootloader unpacks into a temp dir (`sys._MEIPASS`).
2. `launcher.py` detects `sys.frozen`, sets the DB path to `~/.carrera/carrera.db`, sets `PDF_OUTPUT_DIR` to `~/.carrera/pdfs/`, sets `CARRERA_FRONTEND_DIST` to the unpacked frontend folder.
3. Legacy migration: if `~/.careerops/` exists and `~/.carrera/` doesn't, the directory is renamed in place so an upgrader keeps their data.
4. Background thread starts uvicorn on port 18432.
5. Main thread opens a pywebview window titled "Carrera" pointed at the local URL.
6. On window close: the daemon thread dies with the process. SQLite's WAL flushes on the uvicorn shutdown hook.

## Distributing

`dist/Carrera/` is self-contained. Ship it however you like:

- **Zip**: `Compress-Archive dist/Carrera carrera-v1.0.0-win64.zip`. User unzips, runs `Carrera.exe`.
- **Desktop shortcut**: `scripts/install-shortcut.ps1` creates a `.lnk` on the current user's desktop. Safe to run repeatedly (idempotent).
- **Installer**: wrap with Inno Setup or NSIS if you want Start Menu / uninstaller. A template `installer.iss` is **not** in the repo (premature); add one when you actually need it.

## Rebuilding after changes

| Changed | Command |
|---|---|
| Frontend only | `npm run build` → `pyinstaller carrera.spec --noconfirm` |
| Backend only | `pyinstaller carrera.spec --noconfirm` |
| New Python dep | `pip install ...` → add to `backend/requirements.txt` → `pyinstaller carrera.spec --noconfirm` |
| New scraper | Add module to `hiddenimports` in `carrera.spec` → rebuild |

## Troubleshooting

**"WARNING: Hidden import 'xxx' not found".**
PyInstaller couldn't locate the module. Either install it (`pip install xxx`) or it's a false positive (stale reference in the spec).

**Exe starts, window never appears.**
WebView2 Runtime not installed. Windows 11 has it; on Windows 10, download from Microsoft: https://developer.microsoft.com/microsoft-edge/webview2/.

**Exe crashes on launch with `ModuleNotFoundError: No module named 'app'`.**
`launcher.py` inserts `backend/` into `sys.path` — but only if the folder structure in the bundle is right. Verify `dist/Carrera/_internal/backend/app/` exists. If not, check `pathex` and the `datas` tuple in `carrera.spec`.

**Console window flashes open.**
The spec sets `console=False`. If you see a console, you're running from source (fine) or someone edited the spec.

**Exe size ballooned.**
`a.binaries` pulls in every DLL PyInstaller's analyser thinks you need. Check `build/Carrera/warn-Carrera.txt` for surprises. Common culprits: CUDA, Qt, matplotlib. Add to `excludes` in the spec.

## macOS / Linux

The current spec targets Windows only (icon format, pywebview backend). Porting:

- **macOS**: change the icon to `.icns`, set `console=False`, use `pywebview` with the Cocoa backend (default). Sign with `codesign` if you plan to distribute.
- **Linux**: pywebview uses GTK/QT — add `webview.platforms.gtk` (or `qt`) to hidden imports, bundle the matching system libs.

Not tested. Patches welcome.
