"""Webcam and microphone smoke test for Nexus Core (Windows, macOS and Linux).

Run from the repository root with Nexus Core closed:
    python tools/av_smoke_test.py

The test opens the default webcam and microphone briefly. It does not save,
upload, or retain video or audio.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> int:
    try:
        import cv2
        import sounddevice as sd
    except Exception as exc:
        print(f"Missing camera/audio dependency: {exc}")
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.camera import open_camera

    camera = open_camera(0)
    try:
        if camera is None:
            print("FAIL: Could not open the default webcam (index 0).")
            return 1
        ok, frame = camera.read()
        if not ok or frame is None or frame.size == 0:
            print("FAIL: Webcam opened, but no frame could be read.")
            return 1
        print(f"PASS: Webcam opened and delivered a frame ({frame.shape[1]}x{frame.shape[0]}).")
    finally:
        if camera is not None:
            camera.release()

    try:
        devices = sd.query_devices()
        inputs = [
            (index, device)
            for index, device in enumerate(devices)
            if int(device.get("max_input_channels", 0)) > 0
        ]
        if not inputs:
            print("FAIL: No microphone/input device is available to PortAudio.")
            return 1
        default_input = sd.default.device[0]
        if default_input is None or int(default_input) < 0:
            default_input = inputs[0][0]
        device_info = sd.query_devices(default_input, "input")
        channels = 1
        samplerate = int(device_info.get("default_samplerate") or 16000)
        with sd.InputStream(
            device=default_input,
            channels=channels,
            samplerate=samplerate,
            dtype="int16",
        ):
            time.sleep(0.25)
        print(f"PASS: Microphone stream opened ({device_info.get('name')}, {samplerate} Hz).")
    except Exception as exc:
        print(f"FAIL: Could not open a microphone input stream: {exc}")
        return 1

    print("PASS: Basic Windows webcam and microphone hardware checks completed.")
    print("Note: This does not verify Gemini/API credentials or end-to-end speech recognition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
