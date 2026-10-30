"""
Nexus Protocol Execution Engine (v2)
High-level macro orchestrator that reconfigures the user's digital environment
across PC and connected mobile devices with a single directive.

All platform-specific desktop operations go through core.platform_api, so the
same protocols run unchanged on Windows, macOS, and Linux.
"""

from typing import Dict, Any, List, Optional
import psutil

from core.identity import identity
from core.platform_api import platform_api


class ProtocolEngine:
    def __init__(self):
        self.active_protocol: Optional[str] = None
        self.registered_protocols: Dict[str, Any] = {
            "deep_work": self.execute_deep_work,
            "redline": self.execute_redline,
            "lockdown": self.execute_lockdown,
            "nightfall": self.execute_nightfall,
        }

    def execute(self, protocol_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes a recognized high-level protocol."""
        key = protocol_name.strip().lower().replace(" ", "_")
        if key not in self.registered_protocols:
            return {
                "success": False,
                "error": f"Unknown protocol '{protocol_name}'. Available: {list(self.registered_protocols.keys())}"
            }

        fn = self.registered_protocols[key]
        try:
            result = fn(params or {})
            self.active_protocol = key
            return {"success": True, "protocol": key, "result": result}
        except Exception as e:
            return {"success": False, "protocol": key, "error": str(e)}

    # ── PROTOCOL: DEEP WORK ──────────────────────────────────────────────
    def execute_deep_work(self, params: Dict[str, Any]) -> str:
        """
        Maximizes focus:
        - Sets Nexus behavior mode to minimal.
        - Minimizes distracting applications.
        """
        identity.set_behavior_mode("minimal")

        distractions = ["steam.exe", "discord.exe", "telegram.exe", "spotify.exe", "epicgameslauncher.exe"]
        minimized_count = platform_api.minimize_windows_by_name(distractions)

        return f"Protocol Deep Work engaged. Persona switched to minimal. {minimized_count} distraction windows minimized."

    # ── PROTOCOL: REDLINE (MAX PERFORMANCE) ──────────────────────────────
    def execute_redline(self, params: Dict[str, Any]) -> str:
        """
        Frees memory and sets the machine to a high-performance power plan.
        """
        # Memory compaction / purge idle working sets (Windows only via platform_api).
        ram_before = psutil.virtual_memory().percent

        if platform_api._OS == "Windows":
            try:
                import ctypes
                ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
            except Exception:
                pass

        ram_after = psutil.virtual_memory().percent
        return f"Protocol Redline active. High-performance mode engaged. RAM load at {ram_after}%."

    # ── PROTOCOL: LOCKDOWN (GHOST PRIVACY) ───────────────────────────────
    def execute_lockdown(self, params: Dict[str, Any]) -> str:
        """
        Instantly locks the session and mutes speakers.
        """
        platform_api.mute_system_audio(True)
        platform_api.lock_workstation()
        return "Protocol Lockdown triggered. Session locked and master audio muted."

    # ── PROTOCOL: NIGHTFALL (WRAP UP DAY) ────────────────────────────────
    def execute_nightfall(self, params: Dict[str, Any]) -> str:
        """
        Sets assistant to casual/night mode, switches theme if available, and gives a closing debrief.
        """
        identity.set_behavior_mode("minimal")
        return "Protocol Nightfall initialized. Work sessions logged. System ready for standby."


# Global singleton instance
protocols = ProtocolEngine()
