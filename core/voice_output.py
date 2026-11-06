"""
core/voice_output.py
Speak text with an external TTS engine (ElevenLabs / Groq / Fish Audio / Edge).

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

PREVIEW_TEXT = "Hello, this is how I will sound."


def build_provider(engine_id: str | None = None, api_key: str = "", voice: str = "", model: str = ""):
    """Instantiate the saved engine. Explicit api_key / voice / model override saved settings
    (used by the first-run Test button, before anything has been written to disk)."""
    from core.tts_providers import get_tts_provider
    settings = voice_settings.load()
    engine_id = engine_id or voice_settings.engine(settings)
    kwargs = {}
    v = voice or voice_settings.voice(engine_id, settings)
    m = model or voice_settings.model(engine_id, settings)
    if v:
        kwargs["voice_id"] = v
    if m:
        kwargs["model"] = m
    if api_key:
        kwargs["api_key"] = api_key
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


def audio_extension(audio: bytes) -> str:
    """File extension matching the audio bytes (Groq returns WAV, the rest MP3)."""
    head = bytes(audio[:12])
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return ".wav"
    if head[:4] == b"OggS":
        return ".ogg"
    return ".mp3"


def _powershell_play(path: str) -> bool:
    """Windows fallback that plays MP3/WAV with the built-in WPF MediaPlayer."""
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return False
    quoted = path.replace("'", "''")
    script = (
        "Add-Type -AssemblyName presentationCore; "
        "$p = New-Object System.Windows.Media.MediaPlayer; "
        f"$p.Open([uri]'{quoted}'); "
        "$n = 0; while (-not $p.NaturalDuration.HasTimeSpan -and $n -lt 100) { Start-Sleep -Milliseconds 100; $n++ }; "
        "$p.Play(); "
        "if ($p.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds ([int]$p.NaturalDuration.TimeSpan.TotalMilliseconds + 300) }; "
        "$p.Close()"
    )
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run([exe, "-NoProfile", "-Command", script], check=False,
                              timeout=180, creationflags=flags).returncode == 0
    except Exception as exc:
        logger.warning(f"PowerShell playback failed: {exc}")
        return False


def _play_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if sys.platform == "darwin" and shutil.which("afplay"):
        return subprocess.run(["afplay", path], check=False).returncode == 0
    if sys.platform == "win32":
        if ext == ".wav":
            try:
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME)
                return True
            except Exception:
                pass
        for player in ("ffplay", "mpv"):          # nicer when the user has them
            if shutil.which(player):
                break
        else:
            return _powershell_play(path)
    for player in ("ffplay", "mpg123", "mpv"):
        exe = shutil.which(player)
        if exe:
            args = {"ffplay": [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    "mpg123": [exe, "-q", path], "mpv": [exe, "--no-video", "--really-quiet", path]}[player]
            return subprocess.run(args, check=False).returncode == 0
    if ext == ".wav":                              # Linux: WAV can use the stock players
        for player, args in (("paplay", ["paplay"]), ("aplay", ["aplay", "-q"])):
            exe = shutil.which(player)
            if exe:
                return subprocess.run([exe, *args[1:], path], check=False).returncode == 0
    if sys.platform == "win32":
        return _powershell_play(path)
    return False


def _play_audio(audio: bytes) -> bool:
    path = os.path.join(tempfile.gettempdir(), f"nexus_tts_{uuid.uuid4().hex}{audio_extension(audio)}")
    with open(path, "wb") as f:
        f.write(audio)
    try:
        return _play_file(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def speak_external(text: str) -> bool:
    text = (text or "").strip()
    if not text or not external_voice_ready():
        return False
    try:
        provider = build_provider()
        audio = provider.synthesize(text, voice_id=getattr(provider, "voice_id", None) or None)
        if not audio:
            return False
        return _play_audio(audio)
    except Exception as exc:
        logger.error(f"External TTS failed: {exc}")
        return False


def preview_voice(engine_id: str, api_key: str = "", voice: str = "", model: str = "",
                  text: str = PREVIEW_TEXT) -> tuple[bool, str]:
    """Synthesize and play a short sample. Returns (ok, human-readable message).

    Meant for a Test button: nothing has to be saved first, and failures say why
    (bad key, missing package, no audio player) instead of failing silently.
    """
    try:
        provider = build_provider(engine_id, api_key=api_key, voice=voice, model=model)
    except Exception as exc:
        return False, f"Could not start this voice engine: {exc}"
    if provider is None:
        return False, "Unknown voice engine."
    if getattr(provider, "native", False):
        return True, "Gemini's built-in voice is used inside the live session (no separate test needed)."
    if not provider.available:
        return False, provider.init_error or "Not configured - add an API key first."
    try:
        audio = provider.synthesize(text, voice_id=getattr(provider, "voice_id", None) or None)
    except Exception as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
    if not audio:
        return False, getattr(provider, "last_error", "") or "The service returned no audio."
    try:
        played = _play_audio(audio)
    except Exception as exc:
        return False, f"Audio was generated but could not be played: {exc}"
    if not played:
        return True, "Voice works, but no audio player was found to play it here (install ffmpeg or mpv). It will still be saved."
    return True, "Voice works."
