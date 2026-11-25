"""Shared webcam helper: picks the right OpenCV backend per operating system.

Windows -> DirectShow (CAP_DSHOW), macOS -> AVFoundation, Linux -> V4L2.
Every backend falls back to OpenCV's automatic choice (CAP_ANY).
"""
from __future__ import annotations

import sys
from typing import Iterable, List, Optional


def camera_backends(cv2_module=None) -> List[int]:
    """Ordered list of OpenCV backends to try on this OS (always ends in CAP_ANY)."""
    cv2 = cv2_module
    if cv2 is None:
        import cv2  # type: ignore
    preferred: List[Optional[int]] = []
    if sys.platform == "win32":
        preferred.append(getattr(cv2, "CAP_DSHOW", None))
    elif sys.platform == "darwin":
        preferred.append(getattr(cv2, "CAP_AVFOUNDATION", None))
    else:
        preferred.append(getattr(cv2, "CAP_V4L2", None))
    preferred.append(getattr(cv2, "CAP_ANY", 0))
    result: List[int] = []
    for backend in preferred:
        if backend is not None and backend not in result:
            result.append(int(backend))
    return result


def open_camera(
    index: int = 0,
    *,
    indexes: Optional[Iterable[int]] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    require_frame: bool = False,
    cv2_module=None,
):
    """Open a webcam and return an opened cv2.VideoCapture, or None.

    ``indexes`` overrides ``index`` with several candidates tried in order.
    With ``require_frame`` a camera only counts if it delivers one frame.
    """
    cv2 = cv2_module
    if cv2 is None:
        import cv2  # type: ignore
    candidates = list(indexes) if indexes is not None else [index]
    for backend in camera_backends(cv2):
        for idx in candidates:
            cap = None
            try:
                cap = cv2.VideoCapture(int(idx), backend)
                if cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                    continue
                if width:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                if height:
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                if require_frame:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        cap.release()
                        continue
                return cap
            except Exception:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
    return None
