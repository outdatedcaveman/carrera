"""
Carrera desktop launcher.
Starts the FastAPI server in a background thread, then opens a native
pywebview window (Edge WebView2 on Windows 11).
"""
import sys
import os
import threading
import time
import socket
import logging

# ── Path setup for PyInstaller frozen bundle ───────────────────────────────────
if getattr(sys, "frozen", False):
    # Running as compiled .exe — all files extracted to sys._MEIPASS
    BUNDLE_DIR = sys._MEIPASS  # type: ignore[attr-defined]
    # Insert backend directory so `import app` works
    sys.path.insert(0, os.path.join(BUNDLE_DIR, "backend"))
    # Tell the app where its data directory lives (user's home, writable).
    # Prefer ~/.carrera but migrate from the legacy ~/.careerops folder if it
    # exists and the new one doesn't — preserves DBs across the rebrand.
    HOME = os.path.expanduser("~")
    DATA_DIR = os.path.join(HOME, ".carrera")
    LEGACY_DIR = os.path.join(HOME, ".careerops")
    if not os.path.isdir(DATA_DIR) and os.path.isdir(LEGACY_DIR):
        try:
            os.rename(LEGACY_DIR, DATA_DIR)
        except OSError:
            # fall back to using the legacy path directly
            DATA_DIR = LEGACY_DIR
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "pdfs"), exist_ok=True)
    # Choose whichever .db file already exists (migration-friendly)
    db_new = os.path.join(DATA_DIR, "carrera.db")
    db_legacy = os.path.join(DATA_DIR, "careerops.db")
    db_file = db_legacy if (os.path.exists(db_legacy) and not os.path.exists(db_new)) else db_new
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_file}")
    os.environ.setdefault("PDF_OUTPUT_DIR", os.path.join(DATA_DIR, "pdfs"))
    os.environ.setdefault("CARRERA_FRONTEND_DIST", os.path.join(BUNDLE_DIR, "frontend", "dist"))
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(BUNDLE_DIR, "backend"))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{BUNDLE_DIR}/data/carrera.db")
    os.environ.setdefault("PDF_OUTPUT_DIR", os.path.join(BUNDLE_DIR, "data", "pdfs"))
    os.environ.setdefault("CARRERA_FRONTEND_DIST", os.path.join(BUNDLE_DIR, "frontend", "dist"))

PORT = 18432

# Log to a file in the data dir so 500s aren't invisible behind a windowed exe.
# Without this, the only thing the user sees is "Internal Server Error" and we
# have no stack trace to debug from.
def _setup_logging() -> None:
    log_path = os.path.join(
        os.path.expanduser("~"), ".carrera", "carrera.log"
    )
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        # Make sure uvicorn's access + error logs end up here too
        for n in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
            logging.getLogger(n).addHandler(handler)
    except Exception:
        # If we can't open the log file, keep the existing console behavior.
        pass


_setup_logging()
logging.basicConfig(level=logging.WARNING)


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def _run_server(port: int) -> None:
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        # Disable reload in production
        reload=False,
    )


def main() -> None:
    # Start server thread
    server_thread = threading.Thread(target=_run_server, args=(PORT,), daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{PORT}"

    # Show splash while waiting for server
    try:
        import webview

        # Create the window immediately; pywebview will show a blank page until server is up
        window = webview.create_window(
            title="Carrera",
            url=url,
            width=1400,
            height=860,
            min_size=(1024, 600),
            text_select=True,
        )

        def _wait_then_load():
            if not _wait_for_server(PORT, timeout=30):
                window.evaluate_js(
                    "document.body.innerHTML='<h2 style=\"font-family:sans-serif;color:#B91C1C;padding:40px\">"
                    "Server failed to start. Try running Carrera again.</h2>'"
                )
                return
            # Server is up — navigate properly if not already there
            try:
                window.load_url(url)
            except Exception:
                pass

        threading.Thread(target=_wait_then_load, daemon=True).start()
        webview.start(debug=False)

    except ImportError:
        # Fallback: open system browser
        if not _wait_for_server(PORT, timeout=30):
            try:
                import tkinter.messagebox as mb
                mb.showerror("Carrera", "Server failed to start on port 18432.")
            except Exception:
                pass
            return
        import webbrowser
        webbrowser.open(url)
        # Keep alive
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
