"""
core/voice_output.py
Speak text with an external TTS engine (ElevenLabs / Groq / Fish Audio).

Gemini Live replies in its own native voice; this is used for Nexus's own
announcements (briefings, alerts, system messages) when another engine is chosen.
Returns False on any problem so the caller can fall back to the Gemini voice.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

from core import voice_settings

logger = logging.getLogger("VoiceOutput")


def build_provider(engine_id: str | None = None):
    from core.tts_providers import get_tts_provider
    settings = voice_settings.load()
    engine_id = engine_id or voice_settings.engine(settings)
    kwargs = {}
    v = voice_settings.voice(engine_id, settings)
    m = voice_settings.model(engine_id, settings)
    if v:
        kwargs["voice_id"] = v
    if m:
        kwargs["model"] = m
    return get_tts_provider(engine_id, **kwargs)


def external_voice_ready() -> bool:
    eng = voice_settings.engine()
    if eng == voice_settings.DEFAULT_ENGINE:
        return False
    try:
        p = build_provider(eng)
        return bool(p is not None and p.available and not getattr(p, "native", False))
    except Exception:
        return False


def _play_file(path: str) -> bool:
    if sys.platform == "darwin" and shutil.which("afplay"):
        return subprocess.run(["afplay", path], check=False).returncode == 0
    for player in ("ffplay", "mpg123", "mpv"):
        exe = shutil.which(player)
        if exe:
            args = {"ffplay": [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    "mpg123": [exe, "-q", path], "mpv": [exe, "--no-video", "--really-quiet", path]}[player]
            return subprocess.run(args, check=False).returncode == 0
    return False


def speak_external(text: str) -> bool:
    text = (text or "").strip()
    if not text or not external_voice_ready():
        return False
    try:
        provider = build_provider()
        audio = provider.synthesize(text, voice_id=getattr(provider, "voice_id", None) or None)
        if not audio:
            return False
        path = os.path.join(tempfile.gettempdir(), f"nexus_tts_{uuid.uuid4().hex}.mp3")
        with open(path, "wb") as f:
            f.write(audio)
        try:
            return _play_file(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    except Exception as exc:
        logger.error(f"External TTS failed: {exc}")
        return False
