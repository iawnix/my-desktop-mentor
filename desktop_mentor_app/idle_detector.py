"""System idle-time detection."""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import sys


def windows_system_idle_seconds() -> float | None:
    if sys.platform != "win32":
        return None

    class LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):  # type: ignore[attr-defined]
            return None
        tick = ctypes.windll.kernel32.GetTickCount()  # type: ignore[attr-defined]
    except Exception:
        return None
    return float((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0


def gnome_system_idle_seconds() -> float | None:
    gdbus = shutil.which("gdbus")
    if not gdbus or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return None
    try:
        result = subprocess.run(
            [
                gdbus,
                "call",
                "--session",
                "--dest",
                "org.gnome.Mutter.IdleMonitor",
                "--object-path",
                "/org/gnome/Mutter/IdleMonitor/Core",
                "--method",
                "org.gnome.Mutter.IdleMonitor.GetIdletime",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.6,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"(\d+)", result.stdout)
    if not match:
        return None
    return int(match.group(1)) / 1000.0


def xprintidle_system_idle_seconds() -> float | None:
    xprintidle = shutil.which("xprintidle")
    if not xprintidle or not os.environ.get("DISPLAY"):
        return None
    try:
        result = subprocess.run(
            [xprintidle],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.4,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip()) / 1000.0
    except ValueError:
        return None


def system_idle_seconds() -> float | None:
    if sys.platform == "win32":
        return windows_system_idle_seconds()
    idle = gnome_system_idle_seconds()
    if idle is not None:
        return idle
    return xprintidle_system_idle_seconds()
