"""
core/moonshine_stt.py
=====================
Moonshine Speech-to-Text engine for Nexus Core.

Moonshine is a fast, accurate, local ASR model that runs entirely on-device.
It is significantly faster than Whisper and ideal for real-time voice control.

Features:
- Local, offline speech-to-text (no API keys needed)
- Auto-correction of common dictation errors
- Configurable model size (moonshine/base or moonshine/tiny)
- Graceful fallback if dependencies are missing
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("MoonshineSTT")

# Common speech-to-text correction pairs
# (misheard phrase, corrected phrase)
_AUTOCORRECT_PAIRS = [
    # Common dictation errors
    (r"\bthere\b", "their"),
    (r"\bto\b", "too"),
    (r"\byour\b", "you're"),
    (r"\bits\b", "it's"),
    (r"\bcan i\b", "can I"),
    (r"\bi want\b", "I want"),
    (r"\bi need\b", "I need"),
    (r"\bi am\b", "I am"),
    (r"\bi will\b", "I will"),
    (r"\bi would\b", "I would"),
    (r"\bi could\b", "I could"),
    (r"\bi should\b", "I should"),
    (r"\bok\b", "okay"),
    (r"\byea\b", "yeah"),
    (r"\bno\b", "no"),
    (r"\byes\b", "yes"),
    (r"\bhello\b", "hello"),
    (r"\bhi\b", "hi"),
    (r"\bhey\b", "hey"),
    (r"\bnexus\b", "Nexus"),
    (r"\bbrahma\b", "Nexus"),
    # Tech terms
    (r"\bgithub\b", "GitHub"),
    (r"\bpython\b", "Python"),
    (r"\bjavas\b", "Java"),
    (r"\bjavascript\b", "JavaScript"),
    (r"\bhtml\b", "HTML"),
    (r"\bcss\b", "CSS"),
    (r"\bapi\b", "API"),
    (r"\bsql\b", "SQL"),
    (r"\bjson\b", "JSON"),
    (r"\bxml\b", "XML"),
    (r"\bai\b", "AI"),
    (r"\bml\b", "ML"),
    (r"\bgpu\b", "GPU"),
    (r"\bcpu\b", "CPU"),
    (r"\bram\b", "RAM"),
    (r"\bssd\b", "SSD"),
    (r"\bhdd\b", "HDD"),
    # Common contractions
    (r"\bdo not\b", "don't"),
    (r"\bdoes not\b", "doesn't"),
    (r"\bdid not\b", "didn't"),
    (r"\bis not\b", "isn't"),
    (r"\bare not\b", "aren't"),
    (r"\bwas not\b", "wasn't"),
    (r"\bwere not\b", "weren't"),
    (r"\bhave not\b", "haven't"),
    (r"\bhas not\b", "hasn't"),
    (r"\bhad not\b", "hadn't"),
    (r"\bwill not\b", "won't"),
    (r"\bwould not\b", "wouldn't"),
    (r"\bcould not\b", "couldn't"),
    (r"\bshould not\b", "shouldn't"),
    (r"\bcan not\b", "can't"),
    (r"\bi am\b", "I'm"),
    (r"\byou are\b", "you're"),
    (r"\bit is\b", "it's"),
    (r"\bthat is\b", "that's"),
    (r"\bwhat is\b", "what's"),
    (r"\bwho is\b", "who's"),
    (r"\bwhere is\b", "where's"),
    (r"\bwhen is\b", "when's"),
    (r"\bwhy is\b", "why's"),
    (r"\bhow is\b", "how's"),
]


class MoonshineSTT:
    """
    Moonshine-based speech-to-text engine with auto-correction.

    Falls back gracefully if moonshine_onnx is not installed.
    """

    def __init__(self, model_name: str = "moonshine/base", enable_autocorrect: bool = True):
        self.model_name = model_name
        self.enable_autocorrect = enable_autocorrect
        self._model = None
        self._processor = None
        self._available = False
        self._init_error: Optional[str] = None

        self._initialize()

    def _initialize(self) -> None:
        """Attempt to load the Moonshine model."""
        try:
            import moonshine_onnx
            from transformers import AutoTokenizer

            self._model = moonshine_onnx.load_model(self.model_name)
            self._processor = AutoTokenizer.from_pretrained("use-fs/moonshine-base")
            self._available = True
            logger.info(f"Moonshine STT initialized with model: {self.model_name}")
        except ImportError as exc:
            self._init_error = (
                "moonshine_onnx or transformers not installed. "
                "Install with: pip install moonshine_onnx transformers"
            )
            logger.warning(self._init_error)
        except Exception as exc:
            self._init_error = f"Failed to load Moonshine model: {exc}"
            logger.warning(self._init_error)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio bytes to text using Moonshine.

        Args:
            audio_data: Raw PCM audio bytes (int16)
            sample_rate: Sample rate of the audio (should be 16000)

        Returns:
            Transcribed text string
        """
        if not self._available:
            raise RuntimeError(self._init_error or "Moonshine not available")

        try:
            import numpy as np

            # Convert bytes to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # Run Moonshine inference
            result = self._model.transcribe(audio_np)

            if isinstance(result, dict):
                text = result.get("text", "")
            elif isinstance(result, str):
                text = result
            else:
                text = str(result)

            # Apply auto-correction
            if self.enable_autocorrect and text:
                text = self._apply_autocorrect(text)

            return text.strip()

        except Exception as exc:
            logger.error(f"Moonshine transcription failed: {exc}")
            return ""

    def _apply_autocorrect(self, text: str) -> str:
        """Apply common speech-to-text correction pairs."""
        corrected = text
        for pattern, replacement in _AUTOCORRECT_PAIRS:
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
        return corrected

    def transcribe_file(self, file_path: str | Path) -> str:
        """Transcribe an audio file to text."""
        from pathlib import Path as _Path

        path = _Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        import wave

        with wave.open(str(path), "rb") as wf:
            sample_rate = wf.getframerate()
            frames = wf.getnframes()
            audio_data = wf.readframes(frames)

        return self.transcribe(audio_data, sample_rate=sample_rate)


# Singleton instance
_moonshine_stt: Optional[MoonshineSTT] = None


def get_moonshine_stt(
    model_name: str = "moonshine/base", enable_autocorrect: bool = True
) -> MoonshineSTT:
    """Get or create the Moonshine STT singleton."""
    global _moonshine_stt
    if _moonshine_stt is None:
        _moonshine_stt = MoonshineSTT(
            model_name=model_name, enable_autocorrect=enable_autocorrect
        )
    return _moonshine_stt


def is_moonshine_available() -> bool:
    """Check if Moonshine STT is available on this system."""
    try:
        import moonshine_onnx  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def get_available_stt_engines() -> list[dict]:
    """Return list of available STT engines with their status."""
    engines = [
        {
            "id": "moonshine",
            "name": "Moonshine (Local, Fast)",
            "description": "On-device speech-to-text with auto-correction. No API key needed.",
            "available": is_moonshine_available(),
            "default": True,
        },
        {
            "id": "gemini_live",
            "name": "Gemini Live (Cloud)",
            "description": "Cloud-based audio-to-audio via Google Gemini. Requires API key.",
            "available": True,  # Always available if Gemini key is set
            "default": False,
        },
    ]
    return engines
