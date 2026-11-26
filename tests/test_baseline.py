"""Baseline smoke tests (2026-11-26; run by Egon's maintainer every rotation, no AI involved).

Catches the breakage that otherwise goes unseen in a repo without tests: every tracked Python file compiles
and every tracked JavaScript file parses (`node --check`). Nothing is executed. Add behaviour tests beside it.
"""
import py_compile
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _tracked(*globs):
    out = subprocess.run(["git", "ls-files", *globs], cwd=ROOT, capture_output=True, text=True).stdout.split()
    return [ROOT / p for p in out if (ROOT / p).exists() and "node_modules" not in p and "/.archive/" not in p]


PY = _tracked("*.py")
JS = _tracked("*.js", "*.mjs", "*.cjs")


@pytest.mark.parametrize("path", PY or [None], ids=lambda p: str(p.relative_to(ROOT)) if p else "none")
def test_python_compiles(path):
    if path is None:
        pytest.skip("no Python files")
    py_compile.compile(str(path), doraise=True)


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
@pytest.mark.parametrize("path", JS or [None], ids=lambda p: str(p.relative_to(ROOT)) if p else "none")
def test_javascript_parses(path):
    if path is None:
        pytest.skip("no JavaScript files")
    r = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]
