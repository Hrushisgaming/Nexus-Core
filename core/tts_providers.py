"""
core/tts_providers.py
=====================
Multi-provider Text-to-Speech for Nexus Core.

Supports:
- ElevenLabs (cloud, high quality voices)
- Groq TTS (cloud, fast)
- Fish Audio (cloud, voice cloning)
- Gemini Live (built-in audio output)

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

    DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Rachel

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None):
        self.api_key = get_api_key("elevenlabs_api_key", "ELEVENLABS_API_KEY", api_key)
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
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
                "model_id": "eleven_turbo_v2_5",
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
# Registry
# ══════════════════════════════════════════════════════════════════════════════


_PROVIDER_REGISTRY: dict[str, type[TTSProvider]] = {
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
                "available": instance.available,
                "init_error": instance.init_error,
                "voices": instance.voices,
            })
        except Exception as exc:
            providers.append({
                "id": pid,
                "name": cls.name,
                "available": False,
                "init_error": str(exc),
                "voices": [],
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
