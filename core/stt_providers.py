"""
core/stt_providers.py
=====================
Multi-provider Speech-to-Text for Nexus Core.

Supports:
- Moonshine (local, fast, no API key)
- Groq Whisper (cloud, fast)
- ElevenLabs Scribe (cloud, high accuracy)
- Gemini Live (cloud, built-in)

All providers share a common interface:
    transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("STTProviders")


class STTProvider:
    """Base class for all STT providers."""

    name: str = "base"
    available: bool = False
    init_error: Optional[str] = None

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        raise NotImplementedError

    def transcribe_file(self, file_path: str | Path) -> str:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# Moonshine (Local, Fast)
# ══════════════════════════════════════════════════════════════════════════════


class MoonshineProvider(STTProvider):
    name = "moonshine"

    def __init__(self, model_name: str = "moonshine/base", enable_autocorrect: bool = True):
        self.model_name = model_name
        self.enable_autocorrect = enable_autocorrect
        self._model = None
        self._available = False
        self._init_error: Optional[str] = None
        self._initialize()

    def _initialize(self) -> None:
        try:
            import moonshine_onnx
            from transformers import AutoTokenizer

            self._model = moonshine_onnx.load_model(self.model_name)
            self._processor = AutoTokenizer.from_pretrained("use-fs/moonshine-base")
            self._available = True
            logger.info(f"Moonshine STT initialized: {self.model_name}")
        except ImportError as exc:
            self._init_error = "moonshine_onnx/transformers not installed"
            logger.warning(f"Moonshine STT unavailable: {self._init_error}")
        except Exception as exc:
            self._init_error = str(exc)
            logger.warning(f"Moonshine STT failed: {self._init_error}")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self._available:
            raise RuntimeError(self._init_error or "Moonshine not available")
        try:
            import numpy as np
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            result = self._model.transcribe(audio_np)
            if isinstance(result, dict):
                text = result.get("text", "")
            elif isinstance(result, str):
                text = result
            else:
                text = str(result)
            return text.strip()
        except Exception as exc:
            logger.error(f"Moonshine transcription error: {exc}")
            return ""

    def transcribe_file(self, file_path: str | Path) -> str:
        import wave
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        with wave.open(str(path), "rb") as wf:
            sample_rate = wf.getframerate()
            frames = wf.getnframes()
            audio_data = wf.readframes(frames)
        return self.transcribe(audio_data, sample_rate=sample_rate)


# ══════════════════════════════════════════════════════════════════════════════
# Groq Whisper (Cloud)
# ══════════════════════════════════════════════════════════════════════════════


class GroqWhisperProvider(STTProvider):
    name = "groq_whisper"

    def __init__(self, api_key: Optional[str] = None, model: str = "whisper-large-v3"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        if not self.api_key:
            self._init_error = "GROQ_API_KEY not set"
            logger.warning("Groq Whisper unavailable: no API key")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self._available:
            raise RuntimeError(self._init_error or "Groq Whisper not configured")
        try:
            import requests
            files = {"file": ("audio.wav", audio_data, "audio/wav")}
            data = {"model": self.model, "response_format": "text"}
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.text.strip()
            logger.error(f"Groq Whisper error {resp.status_code}: {resp.text[:200]}")
            return ""
        except Exception as exc:
            logger.error(f"Groq Whisper error: {exc}")
            return ""

    def transcribe_file(self, file_path: str | Path) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        with open(path, "rb") as f:
            return self.transcribe(f.read())


# ══════════════════════════════════════════════════════════════════════════════
# ElevenLabs Scribe (Cloud)
# ══════════════════════════════════════════════════════════════════════════════


class ElevenLabsSTTProvider(STTProvider):
    name = "elevenlabs"

    def __init__(self, api_key: Optional[str] = None, model: str = "scribe_v1"):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.model = model
        self._available = bool(self.api_key)
        self._init_error: Optional[str] = None
        if not self.api_key:
            self._init_error = "ELEVENLABS_API_KEY not set"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self._available:
            raise RuntimeError(self._init_error or "ElevenLabs not configured")
        try:
            import requests
            files = {"file": ("audio.wav", audio_data, "audio/wav")}
            data = {"model_id": self.model}
            headers = {"xi-api-key": self.api_key}
            resp = requests.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers=headers,
                files=files,
                data=data,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get("text", "").strip()
            logger.error(f"ElevenLabs STT error {resp.status_code}: {resp.text[:200]}")
            return ""
        except Exception as exc:
            logger.error(f"ElevenLabs STT error: {exc}")
            return ""

    def transcribe_file(self, file_path: str | Path) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        with open(path, "rb") as f:
            return self.transcribe(f.read())


# ══════════════════════════════════════════════════════════════════════════════
# Registry / Factory
# ══════════════════════════════════════════════════════════════════════════════


_PROVIDER_REGISTRY: dict[str, type[STTProvider]] = {
    "moonshine": MoonshineProvider,
    "groq_whisper": GroqWhisperProvider,
    "elevenlabs": ElevenLabsSTTProvider,
}


def get_stt_provider(engine_id: str, **kwargs) -> Optional[STTProvider]:
    """Instantiate an STT provider by ID."""
    cls = _PROVIDER_REGISTRY.get(engine_id)
    if cls is None:
        logger.error(f"Unknown STT engine: {engine_id}")
        return None
    try:
        return cls(**kwargs)
    except Exception as exc:
        logger.error(f"Failed to instantiate STT {engine_id}: {exc}")
        return None


def get_available_stt_engines() -> list[dict]:
    """Return list of STT engines with availability status."""
    engines = []
    for eid, cls in _PROVIDER_REGISTRY.items():
        try:
            instance = cls()
            engines.append({
                "id": eid,
                "name": cls.name,
                "available": instance.available,
                "init_error": instance.init_error,
            })
        except Exception as exc:
            engines.append({
                "id": eid,
                "name": cls.name,
                "available": False,
                "init_error": str(exc),
            })
    return engines


# Default instance manager
_default_provider: Optional[STTProvider] = None


def get_default_stt() -> Optional[STTProvider]:
    """Get the default STT provider (moonshine preferred, falls back gracefully)."""
    global _default_provider
    if _default_provider is None:
        # Try moonshine first
        provider = get_stt_provider("moonshine")
        if provider and provider.available:
            _default_provider = provider
        else:
            # Fall back to groq_whisper if available
            provider = get_stt_provider("groq_whisper")
            if provider and provider.available:
                _default_provider = provider
            else:
                provider = get_stt_provider("elevenlabs")
                if provider and provider.available:
                    _default_provider = provider
    return _default_provider
