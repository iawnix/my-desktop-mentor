"""Compatibility exports for system idle detection.

New code should import from ``desktop_mentor_app.platforms.idle``.
"""
from __future__ import annotations

from .platforms.idle import (
    diagnose_gnome_idle,
    diagnose_xprintidle_idle,
    gnome_system_idle_seconds,
    idle_detection_diagnostics,
    system_idle_seconds,
    windows_system_idle_seconds,
    xprintidle_system_idle_seconds,
)

__all__ = [
    "diagnose_gnome_idle",
    "diagnose_xprintidle_idle",
    "gnome_system_idle_seconds",
    "idle_detection_diagnostics",
    "system_idle_seconds",
    "windows_system_idle_seconds",
    "xprintidle_system_idle_seconds",
]
