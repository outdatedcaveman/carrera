"""GET/PATCH for runtime app settings — primarily AI provider keys.

The frontend Settings page hits these to read and update the LLM keys
without the user touching env vars or .env files. Values are stored in
the ``app_settings`` table via ``settings_store``.

Secret values (anything ending in ``_api_key``) are masked in GET
responses so a curious bystander glancing at devtools doesn't see the
full key — the masked form (last 4 chars) is good enough to confirm
which key is active.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..engine import settings_store

router = APIRouter(prefix="/settings", tags=["settings"])


class AISettings(BaseModel):
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"


class AISettingsRead(BaseModel):
    """What the UI sees on GET — keys are masked."""
    anthropic_api_key_set: bool
    anthropic_api_key_hint: str  # last 4 chars or empty
    anthropic_model: str
    openai_api_key_set: bool
    openai_api_key_hint: str
    openai_model: str
    ollama_base_url: str
    ollama_model: str


class AISettingsUpdate(BaseModel):
    """What the UI sends on PATCH — empty string means "leave unchanged"."""
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    openai_model: str | None = Field(default=None)
    ollama_base_url: str | None = Field(default=None)
    ollama_model: str | None = Field(default=None)


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"…{key[-4:]}"


@router.get("/ai", response_model=AISettingsRead)
def get_ai_settings():
    return AISettingsRead(
        anthropic_api_key_set=bool(settings_store.get("anthropic_api_key")),
        anthropic_api_key_hint=_mask(str(settings_store.get("anthropic_api_key") or "")),
        anthropic_model=str(settings_store.get("anthropic_model") or "claude-haiku-4-5-20251001"),
        openai_api_key_set=bool(settings_store.get("openai_api_key")),
        openai_api_key_hint=_mask(str(settings_store.get("openai_api_key") or "")),
        openai_model=str(settings_store.get("openai_model") or "gpt-4o-mini"),
        ollama_base_url=str(settings_store.get("ollama_base_url") or "http://localhost:11434"),
        ollama_model=str(settings_store.get("ollama_model") or "llama3"),
    )


@router.patch("/ai", response_model=AISettingsRead)
def update_ai_settings(payload: AISettingsUpdate):
    """Patch settings. Field set to ``None`` is ignored; ``""`` clears the value.

    Also guards against a recurring user mistake: pasting an API key into
    the model field. We reject any *_model value that looks like an API key
    (starts with ``sk-`` and is long enough), with a 400 explaining where
    it should go.
    """
    updates = payload.model_dump(exclude_none=True)

    for k in ("anthropic_model", "openai_model"):
        v = updates.get(k)
        if v and isinstance(v, str) and v.startswith("sk-") and len(v) > 30:
            raise HTTPException(
                400,
                f"That looks like an API key, not a model name. "
                f"Paste it into the matching API key field instead.",
            )

    try:
        settings_store.set_many(updates)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return get_ai_settings()
