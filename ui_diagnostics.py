"""First-launch checks for microphone and Gemini Live connectivity."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from core.user_paths import get_user_data_dir


class FirstRunDiagnosticsDialog(QDialog):
    """A small first-run checklist that verifies the actual voice path."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nexus Core — First-run diagnostics")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog { background: #0b0f19; color: #ffffff; }
            QLabel { color: #ffffff; background: transparent; }
            QPushButton {
                background: #00e5ff; color: #050a12; border: 0;
                border-radius: 8px; padding: 9px 18px; font-weight: 700;
            }
            QPushButton:disabled { background: #303844; color: #9aa4b2; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Let's check your voice setup")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        subtitle = QLabel(
            "Nexus will check microphone access, your Gemini API key, "
            "and whether a Gemini Live voice session can connect."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #aab5c4; font-size: 12px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.rows = {}
        for key, heading in (
            ("microphone", "Microphone access"),
            ("api_key", "Gemini API key"),
            ("voice", "Gemini Live voice connection"),
        ):
            heading_label = QLabel(heading)
            heading_label.setStyleSheet("font-weight: 700; margin-top: 8px;")
            status_label = QLabel("Waiting to run")
            status_label.setStyleSheet("color: #9aa4b2;")
            status_label.setWordWrap(True)
            layout.addWidget(heading_label)
            layout.addWidget(status_label)
            self.rows[key] = status_label

        self.note = QLabel("Running checks shortly…")
        self.note.setStyleSheet("color: #aab5c4; font-size: 11px;")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.rerun_button = QPushButton("Run again")
        self.rerun_button.clicked.connect(self.run_checks)
        self.continue_button = QPushButton("Continue")
        self.continue_button.clicked.connect(self.accept)
        buttons.addWidget(self.rerun_button)
        buttons.addWidget(self.continue_button)
        layout.addLayout(buttons)

        QTimer.singleShot(250, self.run_checks)

    def _set_status(self, key: str, ok: bool | None, detail: str):
        label = self.rows[key]
        if ok is True:
            label.setStyleSheet("color: #63d9a5;")
            prefix = "PASS"
        elif ok is False:
            label.setStyleSheet("color: #ffad82;")
            prefix = "CHECK"
        else:
            label.setStyleSheet("color: #9aa4b2;")
            prefix = "SKIP"
        label.setText(f"{prefix} — {detail}")

    @staticmethod
    def _get_api_key() -> str:
        for path in (
            get_user_data_dir() / "config" / "app_settings.json",
            get_user_data_dir() / "config" / "api_keys.json",
        ):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                key = str(data.get("gemini_api_key", "") or "").strip()
                if key:
                    return key
            except (OSError, ValueError, TypeError):
                continue
        return (
            os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        ).strip()

    @staticmethod
    def _check_microphone() -> tuple[bool, str]:
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            input_device = sd.default.device[0]
            if input_device is None or int(input_device) < 0:
                candidates = [
                    (index, device) for index, device in enumerate(devices)
                    if int(device.get("max_input_channels", 0)) > 0
                ]
                if not candidates:
                    return False, "No microphone input device was found."
                input_device = candidates[0][0]

            # Opening a short-lived stream triggers macOS microphone permission
            # handling and verifies that PortAudio can actually capture input.
            with sd.InputStream(
                device=input_device, samplerate=16000, channels=1, blocksize=256
            ):
                time.sleep(0.15)
            return True, "Microphone opened successfully; no audio was saved."
        except Exception as exc:
            return False, f"Microphone unavailable or permission denied: {exc}"

    @staticmethod
    def _check_live_connection(api_key: str) -> tuple[bool, str]:
        if not api_key:
            return False, "Add a Gemini API key in Settings → AI Providers."

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key, http_options={"api_version": "v1beta"}
            )
            discovered = []
            for model_info in client.models.list():
                name = str(getattr(model_info, "name", "") or "").strip()
                if not name:
                    continue
                lowered = name.lower()
                if "live" in lowered or "native-audio" in lowered:
                    if not name.startswith("models/"):
                        name = f"models/{name}"
                    if name not in discovered:
                        discovered.append(name)

            fallbacks = (
                "models/gemini-2.5-flash-native-audio-preview-12-2025",
                "models/gemini-3.1-flash-live-preview",
            )
            candidates = discovered + [m for m in fallbacks if m not in discovered]
            if not candidates:
                return False, "The API key works, but no Gemini Live model was listed."

            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Charon"
                        )
                    )
                ),
            )

            async def connect_once(model: str):
                async with client.aio.live.connect(model=model, config=config):
                    return model

            last_error = None
            for model in candidates:
                try:
                    connected_model = asyncio.run(
                        asyncio.wait_for(connect_once(model), timeout=10)
                    )
                    return True, f"Gemini Live connected successfully ({connected_model})."
                except Exception as exc:
                    last_error = exc
            return False, f"Gemini Live connection failed: {last_error}"
        except Exception as exc:
            return False, f"Gemini voice service check failed: {exc}"

    def run_checks(self):
        self.rerun_button.setEnabled(False)
        self.note.setText("Checking microphone…")
        self._set_status("microphone", None, "Checking…")
        self._set_status("api_key", None, "Checking…")
        self._set_status("voice", None, "Waiting…")
        self.repaint()

        mic_ok, mic_detail = self._check_microphone()
        self._set_status("microphone", mic_ok, mic_detail)

        api_key = self._get_api_key()
        key_ok = bool(api_key)
        self._set_status(
            "api_key", key_ok,
            "Gemini API key found." if key_ok else "No Gemini API key found in settings or environment."
        )

        self.note.setText("Testing a real Gemini Live connection…")
        self.repaint()
        voice_ok, voice_detail = self._check_live_connection(api_key)
        self._set_status("voice", voice_ok, voice_detail)

        if mic_ok and key_ok and voice_ok:
            self.note.setText("All voice checks passed. Nexus is ready.")
        else:
            self.note.setText(
                "Some checks need attention. You can continue and fix them later in Settings."
            )
        self.rerun_button.setEnabled(True)
