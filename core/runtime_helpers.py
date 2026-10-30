"""Small, dependency-light helpers used by the Nexus Core runtime."""
from __future__ import annotations

import socket


def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _extract_gemini_text(response) -> str:
    text_parts: list[str] = []
    try:
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    text_parts.append(part_text)
    except Exception:
        pass

    text = "".join(text_parts).strip()
    if text:
        return text

    try:
        return (getattr(response, "text", "") or "").strip()
    except Exception:
        return ""


def _build_task_plan(text: str) -> list[str]:
    t = (text or "").lower()
    if any(word in t for word in ("presentation", "ppt", "slides", "deck")):
        return [
            "Understand the topic and goal",
            "Build a slide structure",
            "Generate and format the deck",
            "Open the finished presentation",
        ]
    if any(word in t for word in ("spreadsheet", "excel", "sheet", "table", "tracker", "budget")):
        return [
            "Read the data request",
            "Lay out sheets and columns",
            "Apply formulas and formatting",
            "Open the workbook",
        ]
    if any(word in t for word in ("word", "docx", "document", "report", "letter")):
        return [
            "Understand the document type",
            "Draft the structure and content",
            "Preserve formatting and polish",
            "Save the editable file",
        ]
    if any(word in t for word in ("website", "web site", "landing page", "saaS", "saas", "dashboard", "app")):
        return [
            "Interpret the brief",
            "Generate frontend and backend files",
            "Launch the local preview",
            "Debug and fix launch issues if needed",
        ]
    if any(word in t for word in ("browser", "website", "google", "search", "open url", "navigate")):
        return [
            "Open the browser",
            "Navigate to the target page",
            "Collect the needed information",
            "Return the result",
        ]
    if any(word in t for word in ("screen", "camera", "meeting", "call", "analyze", "analyse", "analyze")):
        return [
            "Capture the live screen or camera",
            "Inspect what is visible",
            "Answer with the important details",
            "Keep listening for follow-up commands",
        ]
    if any(word in t for word in ("fan", "light", "plug", "kasa", "atomberg", "smart home", "home device", "room", "bedroom", "living room", "kitchen", "office", "bathroom", "balcony")):
        return [
            "Identify the smart-home device or room",
            "Choose the correct action",
            "Send the command to the connected provider",
            "Confirm the result back to the user",
        ]
    return [
        "Understand the command",
        "Choose the right tool",
        "Execute the task",
        "Return the result",
    ]
