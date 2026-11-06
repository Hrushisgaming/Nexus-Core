"""
core/tts_providers.py
=====================
Multi-provider Text-to-Speech for Nexus Core.

Supports:
- ElevenLabs (cloud, high quality voices)
- Groq TTS (cloud, fast)
- Fish Audio (cloud, voice cloning)
- Microsoft Edge voices (free, no API key)
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
    needs_key: bool = True          # False = works without any API key
    last_error: str = ""            # why the most recent synthesize() failed ('' = no failure)

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

    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: Optional[str] = None):
        self.api_key = get_api_key("elevenlabs_api_key", "ELEVENLABS_API_KEY", api_key)
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model = model or self.default_model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        self.voices = [
            {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "description": "Warm, versatile female voice"},
            {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "description": "Deep, authoritative male voice"},
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
            self.last_error = ""
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.content
            self.last_error = f"HTTP {resp.status_code}: {resp.text[:160]}"
            logger.error(f"ElevenLabs TTS error {self.last_error}")
            return b""
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            logger.error(f"ElevenLabs TTS error: {exc}")
            return b""

    def get_voices(self) -> list[dict]:
        return self.voices


# ══════════════════════════════════════════════════════════════════════════════
# Groq TTS (PlayHT / Orpheus)
# ══════════════════════════════════════════════════════════════════════════════


class GroqTTSProvider(TTSProvider):
    """Groq's text-to-speech (Canopy Labs Orpheus). PlayAI TTS was retired by Groq.

    Groq returns WAV only, and Orpheus accepts short inputs, so long text is sent
    in sentence-sized pieces and the WAV parts are joined.
    """
    name = "groq_tts"
    label = "Groq TTS"
    default_model = "canopylabs/orpheus-v1-english"
    suggested_models = ["canopylabs/orpheus-v1-english"]
    audio_format = "wav"

    DEFAULT_VOICE_ID = "autumn"
    LEGACY_MODELS = {"playai-tts", "playai-tts-arabic"}   # retired -> mapped to default_model
    MAX_CHARS = 190

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: Optional[str] = None):
        self.api_key = get_api_key("groq_api_key", "GROQ_API_KEY", api_key)
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        if not model or model in self.LEGACY_MODELS:
            model = self.default_model
        self.model = model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        self.voices = [
            {"id": "autumn", "name": "Autumn", "description": "Warm female voice (default)"},
            {"id": "diana", "name": "Diana", "description": "Clear female voice"},
            {"id": "hannah", "name": "Hannah", "description": "Friendly female voice"},
            {"id": "austin", "name": "Austin", "description": "Natural male voice"},
            {"id": "daniel", "name": "Daniel", "description": "Calm male voice"},
            {"id": "troy", "name": "Troy", "description": "Deep male voice"},
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

    @staticmethod
    def _split_text(text: str, limit: int) -> list[str]:
        import re
        chunks: list[str] = []
        cur = ""
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
            while len(sentence) > limit:                      # hard-split very long sentences
                cut = sentence.rfind(" ", 0, limit)
                cut = cut if cut > 0 else limit
                if cur:
                    chunks.append(cur)
                    cur = ""
                chunks.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if cur and len(cur) + 1 + len(sentence) > limit:
                chunks.append(cur)
                cur = sentence
            else:
                cur = f"{cur} {sentence}".strip()
        if cur:
            chunks.append(cur)
        return [c for c in chunks if c]

    @staticmethod
    def _join_wavs(parts: list[bytes]) -> bytes:
        if len(parts) == 1:
            return parts[0]
        import io
        import wave
        try:
            with wave.open(io.BytesIO(parts[0]), "rb") as first:
                params = first.getparams()
            out = io.BytesIO()
            with wave.open(out, "wb") as dst:
                dst.setparams(params)
                for part in parts:
                    with wave.open(io.BytesIO(part), "rb") as src:
                        dst.writeframes(src.readframes(src.getnframes()))
            return out.getvalue()
        except Exception as exc:
            logger.warning(f"Groq TTS: could not join audio parts ({exc}); using the first part")
            return parts[0]

    def _request(self, text: str, voice: str) -> tuple[int, bytes, str]:
        import requests
        resp = requests.post(
            "https://api.groq.com/openai/v1/audio/speech",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": text, "voice": voice, "response_format": "wav"},
            timeout=45,
        )
        return resp.status_code, (resp.content if resp.status_code == 200 else b""), (resp.text or "")[:160]

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not self._available:
            raise RuntimeError(self._init_error or "Groq TTS not configured")
        self.last_error = ""
        voice = voice_id or self.voice_id
        parts: list[bytes] = []
        try:
            for chunk in self._split_text(text, self.MAX_CHARS):
                status, audio, body = self._request(chunk, voice)
                if status == 400 and voice != self.DEFAULT_VOICE_ID and "voice" in body.lower():
                    # an old / unknown voice name saved in settings: fall back to the default voice
                    voice = self.DEFAULT_VOICE_ID
                    status, audio, body = self._request(chunk, voice)
                if status != 200:
                    hint = " (key rejected - check it is a Groq key)" if status in (401, 403) else ""
                    self.last_error = f"HTTP {status}{hint}: {body}"
                    logger.error(f"Groq TTS error {self.last_error}")
                    return b""
                parts.append(audio)
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            logger.error(f"Groq TTS error: {exc}")
            return b""
        return self._join_wavs(parts) if parts else b""

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
            self.last_error = ""
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.content
            self.last_error = f"HTTP {resp.status_code}: {resp.text[:160]}"
            logger.error(f"Fish Audio TTS error {self.last_error}")
            return b""
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            logger.error(f"Fish Audio TTS error: {exc}")
            return b""

    def get_voices(self) -> list[dict]:
        return self.voices



# ══════════════════════════════════════════════════════════════════════════════
# Microsoft Edge voices (free, no API key)
# ══════════════════════════════════════════════════════════════════════════════


class EdgeTTSProvider(TTSProvider):
    name = "edge_tts"
    label = "Microsoft Edge (free, no key)"
    default_model = ""
    suggested_models: list[str] = []
    needs_key = False

    DEFAULT_VOICE_ID = "en-US-GuyNeural"

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None, model: Optional[str] = None):
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model = model or ""
        self._init_error: Optional[str] = None
        try:
            import edge_tts  # noqa: F401
            self._available = True
        except Exception:
            self._available = False
            self._init_error = "edge-tts is not installed (pip install edge-tts)"
        self.voices = [
            {"id": "en-US-GuyNeural", "name": "Guy", "description": "US male, natural"},
            {"id": "en-US-AriaNeural", "name": "Aria", "description": "US female, expressive"},
            {"id": "en-US-JennyNeural", "name": "Jenny", "description": "US female, friendly"},
            {"id": "en-US-AndrewNeural", "name": "Andrew", "description": "US male, warm"},
            {"id": "en-GB-RyanNeural", "name": "Ryan", "description": "UK male"},
            {"id": "en-GB-SoniaNeural", "name": "Sonia", "description": "UK female"},
            {"id": "en-IN-NeerjaNeural", "name": "Neerja", "description": "Indian English female"},
            {"id": "en-IN-PrabhatNeural", "name": "Prabhat", "description": "Indian English male"},
        ]

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not self._available:
            raise RuntimeError(self._init_error or "Edge TTS not available")
        self.last_error = ""
        voice = voice_id or self.voice_id

        async def _run() -> bytes:
            import edge_tts
            audio = bytearray()
            async for chunk in edge_tts.Communicate(text, voice=voice).stream():
                if chunk.get("type") == "audio":
                    audio.extend(chunk.get("data", b""))
            return bytes(audio)

        try:
            import asyncio
            import threading
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(_run())
            box: dict = {}                                    # called from inside an event loop

            def _worker():
                try:
                    box["audio"] = asyncio.run(_run())
                except Exception as exc:
                    box["error"] = exc
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            t.join(60)
            if "error" in box:
                raise box["error"]
            return box.get("audio", b"")
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            logger.error(f"Edge TTS error: {exc}")
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
    "edge_tts": EdgeTTSProvider,
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
                "needs_key": cls.needs_key,
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
                "needs_key": cls.needs_key,
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
    """Get the default TTS provider (ElevenLabs preferred, then Groq, then Fish Audio, then free Edge)."""
    global _default_provider
    if _default_provider is None:
        for pid in ("elevenlabs", "groq_tts", "fish_audio", "edge_tts"):
            provider = get_tts_provider(pid)
            if provider and provider.available:
                _default_provider = provider
                break
    return _default_provider
