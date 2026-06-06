"""Runtime app settings — DB-backed overrides for ``Settings``.

Why a separate layer? The Pydantic ``Settings`` class reads from environment
variables / .env at process start. That works fine for CLI use, but the
desktop app has no ``.env`` and asking users to set Windows environment
variables for an API key is a UX dead-end. So we keep an ``app_settings``
key-value table the user can write through the Settings UI, and expose a
single ``get(key)`` helper that prefers the DB value over the env one.

Values are JSON-encoded in the DB so the store can hold strings, numbers,
or small objects without extra columns.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..database import SessionLocal
from ..models import AppSetting
from ..config import get_settings

logger = logging.getLogger(__name__)

# Keys exposed to the UI. Anything not in this set is ignored on write.
ALLOWED_KEYS = {
    "anthropic_api_key",
    "anthropic_model",
    "openai_api_key",
    "openai_model",
    "ollama_base_url",
    "ollama_model",
}


def _read_db(key: str) -> Any | None:
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row is None:
            return None
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            return row.value  # legacy/raw fallback
    finally:
        db.close()


def get(key: str, default: Any = None) -> Any:
    """Return the DB value if set, otherwise fall back to ``Settings`` (env)."""
    db_val = _read_db(key)
    if db_val not in (None, ""):
        return db_val
    env_val = getattr(get_settings(), key, None)
    if env_val not in (None, ""):
        return env_val
    return default


def set_value(key: str, value: Any) -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Setting '{key}' is not in the allowed list")
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        encoded = json.dumps(value)
        if row is None:
            db.add(AppSetting(key=key, value=encoded))
        else:
            row.value = encoded
        db.commit()
    finally:
        db.close()


def set_many(updates: dict[str, Any]) -> None:
    for k, v in updates.items():
        if k in ALLOWED_KEYS:
            set_value(k, v)


def get_all() -> dict[str, Any]:
    """Return every UI-exposed setting, preferring DB values over env."""
    return {k: get(k, "") for k in ALLOWED_KEYS}


def has_llm_configured() -> bool:
    """Quick check used by import flow to warn when no LLM is available."""
    return bool(get("anthropic_api_key")) or bool(get("openai_api_key"))
