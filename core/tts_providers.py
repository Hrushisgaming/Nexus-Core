"""
core/tts_providers.py
=====================
Multi-provider Text-to-Speech for Nexus Core.

Supports:
- ElevenLabs (cloud, high quality voices)
- Groq TTS (cloud, fast)
- Fish Audio (cloud, voice cloning)
- Gemini Live (built-in native voice, default engine)

Common interface:
    synthesize(text: str) -> bytes  # Returns MP3/WAV audio bytes
    get_voices() -> list[dict]
"""

from __future__ import annotations

import logging
import os
from core.api_keys import get_api_key
from pathlib import Path
from typing import Optional

logger = logging.getLogger("TTSProviders")


class TTSProvider:
    """Base class for TTS providers."""

    name: str = "base"
    label: str = ""                 # display name in Settings
    native: bool = False            # True = audio comes from the model itself (no synthesize())
    default_model: str = ""
    suggested_models: list[str] = []
    available: bool = False
    init_error: Optional[str] = None
    voices: list[dict] = []

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        raise NotImplementedError

    def get_voices(self) -> list[dict]:
        return self.voices


# ══════════════════════════════════════════════════════════════════════════════
# ElevenLabs TTS
# ══════════════════════════════════════════════════════════════════════════════


class ElevenLabsTTSProvider(TTSProvider):
    name = "elevenlabs"
    label = "ElevenLabs"
    default_model = "eleven_turbo_v2_5"
    suggested_models = ["eleven_turbo_v2_5", "eleven_flash_v2_5", "eleven_multilingual_v2", "eleven_v3"]

    DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Rachel

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: Optional[str] = None):
        self.api_key = get_api_key("elevenlabs_api_key", "ELEVENLABS_API_KEY", api_key)
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model = model or self.default_model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        self.voices = [
            {"id": "pNInz6obpgDQGcFmaJgB", "name": "Rachel", "description": "Warm, versatile female voice"},
            {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Adam", "description": "Deep, authoritative male voice"},
            {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi", "description": "Strong, confident female voice"},
            {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "description": "Warm, expressive female voice"},
            {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni", "description": "Professional male voice"},
            {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli", "description": "Young, energetic female voice"},
        ]
        if not self.api_key:
            self._init_error = "ELEVENLABS_API_KEY not set"
            logger.warning("ElevenLabs TTS unavailable: no API key")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not self._available:
            raise RuntimeError(self._init_error or "ElevenLabs not configured")
        try:
            import requests
            vid = voice_id or self.voice_id
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "text": text,
                "model_id": self.model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.content
            logger.error(f"ElevenLabs TTS error {resp.status_code}: {resp.text[:200]}")
            return b""
        except Exception as exc:
            logger.error(f"ElevenLabs TTS error: {exc}")
            return b""

    def get_voices(self) -> list[dict]:
        return self.voices


# ══════════════════════════════════════════════════════════════════════════════
# Groq TTS (PlayHT / Orpheus)
# ══════════════════════════════════════════════════════════════════════════════


class GroqTTSProvider(TTSProvider):
    name = "groq_tts"
    label = "Groq TTS"
    default_model = "playai-tts"
    suggested_models = ["playai-tts", "canopylabs/orpheus-v1-english"]

    DEFAULT_VOICE_ID = "troy"  # Orpheus / Canopy Labs default

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: str = "playai-tts"):
        self.api_key = get_api_key("groq_api_key", "GROQ_API_KEY", api_key)
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model = model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        self.voices = [
            {"id": "troy", "name": "Troy", "description": "Deep, warm male voice (Orpheus/Canopy Labs)"},
            {"id": "fortuna", "name": "Fortuna", "description": "Clear, professional female voice"},
            {"id": "alex", "name": "Alex", "description": "Neutral male voice"},
            {"id": "cody", "name": "Cody", "description": "Friendly male voice"},
            {"id": "jules", "name": "Jules", "description": "Calm male voice"},
            {"id": "kael", "name": "Kael", "description": "Young male voice"},
            {"id": "vicente", "name": "Vicente", "description": "Spanish male voice"},
            {"id": "zephyr", "name": "Zephyr", "description": "Bright female voice"},
        ]
        if not self.api_key:
            self._init_error = "GROQ_API_KEY not set"
            logger.warning("Groq TTS unavailable: no API key")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not self._available:
            raise RuntimeError(self._init_error or "Groq TTS not configured")
        try:
            import requests
            vid = voice_id or self.voice_id
            url = "https://api.groq.com/openai/v1/audio/speech"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "input": text,
                "voice": vid,
                "response_format": "mp3",
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.content
            logger.error(f"Groq TTS error {resp.status_code}: {resp.text[:200]}")
            return b""
        except Exception as exc:
            logger.error(f"Groq TTS error: {exc}")
            return b""

    def get_voices(self) -> list[dict]:
        return self.voices


# ══════════════════════════════════════════════════════════════════════════════
# Fish Audio TTS
# ══════════════════════════════════════════════════════════════════════════════


class FishAudioTTSProvider(TTSProvider):
    name = "fish_audio"
    label = "Fish Audio"
    default_model = "fish-speech-1"
    suggested_models = ["fish-speech-1", "s1"]

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: str = "fish-speech-1"):
        self.api_key = get_api_key("fish_audio_api_key", "FISH_AUDIO_API_KEY", api_key)
        self.voice_id = voice_id or ""
        self.model = model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        self.voices = [
            {"id": "", "name": "Default", "description": "Default Fish Audio voice"},
        ]
        if not self.api_key:
            self._init_error = "FISH_AUDIO_API_KEY not set"
            logger.warning("Fish Audio TTS unavailable: no API key")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not self._available:
            raise RuntimeError(self._init_error or "Fish Audio not configured")
        try:
            import requests
            vid = voice_id or self.voice_id
            url = "https://api.fish.audio/v1/tts"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "text": text,
                "model": self.model,
                "voice_id": vid,
                "format": "mp3",
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.content
            logger.error(f"Fish Audio TTS error {resp.status_code}: {resp.text[:200]}")
            return b""
        except Exception as exc:
            logger.error(f"Fish Audio TTS error: {exc}")
            return b""

    def get_voices(self) -> list[dict]:
        return self.voices



# ══════════════════════════════════════════════════════════════════════════════
# Gemini Live (built-in native voice) - the default engine
# ══════════════════════════════════════════════════════════════════════════════

GEMINI_VOICES = [
    "Charon", "Puck", "Kore", "Fenrir", "Aoede", "Leda", "Orus", "Zephyr",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]


class GeminiLiveTTSProvider(TTSProvider):
    """The voice built into the Gemini Live session. Audio is produced by the model, not synthesized here."""

    name = "gemini_live"
    label = "Gemini Live (built-in)"
    native = True
    default_model = "models/gemini-2.5-flash-native-audio-preview-12-2025"
    suggested_models = [
        "models/gemini-2.5-flash-native-audio-preview-12-2025",
        "models/gemini-2.5-flash-native-audio-latest",
        "models/gemini-3.1-flash-live-preview",
    ]
    DEFAULT_VOICE_ID = "Charon"

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: Optional[str] = None):
        self.api_key = get_api_key("gemini_api_key", "GEMINI_API_KEY", api_key)
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model = model or self.default_model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None if self.api_key else "Gemini API key not set"
        self.voices = [{"id": v, "name": v, "description": "Gemini prebuilt voice"} for v in GEMINI_VOICES]

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        raise RuntimeError("Gemini Live speaks natively inside the live session")

    def get_voices(self) -> list[dict]:
        return self.voices

# ══════════════════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════════════════


_PROVIDER_REGISTRY: dict[str, type[TTSProvider]] = {
    "gemini_live": GeminiLiveTTSProvider,
    "elevenlabs": ElevenLabsTTSProvider,
    "groq_tts": GroqTTSProvider,
    "fish_audio": FishAudioTTSProvider,
}


def get_tts_provider(provider_id: str, **kwargs) -> Optional[TTSProvider]:
    """Instantiate a TTS provider by ID."""
    cls = _PROVIDER_REGISTRY.get(provider_id)
    if cls is None:
        logger.error(f"Unknown TTS provider: {provider_id}")
        return None
    try:
        return cls(**kwargs)
    except Exception as exc:
        logger.error(f"Failed to instantiate TTS {provider_id}: {exc}")
        return None


def get_available_tts_providers() -> list[dict]:
    """Return list of TTS providers with availability status."""
    providers = []
    for pid, cls in _PROVIDER_REGISTRY.items():
        try:
            instance = cls()
            providers.append({
                "id": pid,
                "name": cls.name,
                "label": cls.label or cls.name,
                "native": cls.native,
                "available": instance.available,
                "init_error": instance.init_error,
                "voices": instance.voices,
                "default_voice": getattr(instance, "voice_id", "") or "",
                "default_model": cls.default_model,
                "models": list(cls.suggested_models),
            })
        except Exception as exc:
            providers.append({
                "id": pid,
                "name": cls.name,
                "label": cls.label or cls.name,
                "native": cls.native,
                "available": False,
                "init_error": str(exc),
                "voices": [],
                "default_voice": "",
                "default_model": cls.default_model,
                "models": list(cls.suggested_models),
            })
    return providers


# Default instance manager
_default_provider: Optional[TTSProvider] = None


def get_default_tts() -> Optional[TTSProvider]:
    """Get the default TTS provider (ElevenLabs preferred, then Groq, then Fish Audio)."""
    global _default_provider
    if _default_provider is None:
        for pid in ("elevenlabs", "groq_tts", "fish_audio"):
            provider = get_tts_provider(pid)
            if provider and provider.available:
                _default_provider = provider
                break
    return _default_provider
