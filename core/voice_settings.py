"""
core/voice_settings.py
Single reader for the voice-engine choice saved by Settings.

app_settings.json keys:
    tts_engine : "gemini_live" (default) | "elevenlabs" | "groq_tts" | "fish_audio"
    tts_voices : {engine_id: voice name / id}
    tts_models : {engine_id: model id / name}
    tts_voice_id : legacy single voice id (only honoured for ElevenLabs)
"""
from __future__ import annotations

from typing import Any, Optional

DEFAULT_ENGINE = "gemini_live"
DEFAULT_GEMINI_VOICE = "Charon"


def load() -> dict[str, Any]:
    try:
        from core.atomic_io import read_json_dict
        from core.user_paths import get_user_data_dir
        return read_json_dict(get_user_data_dir() / "config" / "app_settings.json") or {}
    except Exception:
        return {}


def engine(settings: Optional[dict] = None) -> str:
    s = settings if settings is not None else load()
    eng = str(s.get("tts_engine") or DEFAULT_ENGINE).strip()
    return eng or DEFAULT_ENGINE


def voice(engine_id: str, settings: Optional[dict] = None) -> str:
    """Saved voice for an engine ('' means: use the provider's own default)."""
    s = settings if settings is not None else load()
    per = s.get("tts_voices")
    if isinstance(per, dict) and str(per.get(engine_id) or "").strip():
        return str(per[engine_id]).strip()
    if engine_id == "elevenlabs":
        return str(s.get("tts_voice_id") or "").strip()
    return ""


def model(engine_id: str, settings: Optional[dict] = None) -> str:
    s = settings if settings is not None else load()
    per = s.get("tts_models")
    if isinstance(per, dict):
        return str(per.get(engine_id) or "").strip()
    return ""


def gemini_voice_name(settings: Optional[dict] = None) -> str:
    """Prebuilt Gemini voice (names are case-sensitive, e.g. 'Charon')."""
    v = voice("gemini_live", settings)
    return v[:1].upper() + v[1:] if v else DEFAULT_GEMINI_VOICE


def gemini_live_model(settings: Optional[dict] = None) -> str:
    m = model("gemini_live", settings)
    if m and not m.startswith("models/"):
        m = f"models/{m}"
    return m
