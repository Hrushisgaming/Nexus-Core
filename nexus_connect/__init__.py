"""Nexus Connect subsystem.

This package adds the local gateway, device registry, pairing flow, and
protocol definitions used by Nexus AI to reach companion devices.
"""

from .service import NexusConnectService, get_service

__all__ = ["NexusConnectService", "get_service"]
