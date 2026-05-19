"""System idle-time detection."""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import sys
from typing import Any


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


def idle_detection_diagnostics() -> dict[str, Any]:
    """Return a side-channel diagnostic report without changing idle detection behavior."""
    attempts: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None

    if sys.platform == "win32":
        win32_idle = windows_system_idle_seconds()
        selected = {
            "backend": "windows",
            "ok": win32_idle is not None,
            "idle_seconds": win32_idle,
            "status": "ok" if win32_idle is not None else "unavailable",
        }
        attempts.append(selected)
    else:
        gnome_attempt = diagnose_gnome_idle()
        attempts.append(gnome_attempt)
        if gnome_attempt["ok"]:
            selected = gnome_attempt
        else:
            xprintidle_attempt = diagnose_xprintidle_idle()
            attempts.append(xprintidle_attempt)
            if xprintidle_attempt["ok"]:
                selected = xprintidle_attempt

    if selected is None:
        selected = {
            "backend": "fallback",
            "ok": False,
            "idle_seconds": None,
            "status": "system idle unavailable; app will use pet-local interaction timer",
        }

    return {
        "selected": selected,
        "attempts": attempts,
        "environment": {
            "platform": sys.platform,
            "DISPLAY": os.environ.get("DISPLAY", ""),
            "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
            "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
            "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", ""),
            "XAUTHORITY": os.environ.get("XAUTHORITY", ""),
        },
    }


def diagnose_gnome_idle() -> dict[str, Any]:
    gdbus = shutil.which("gdbus")
    if not gdbus:
        return {
            "backend": "gnome",
            "ok": False,
            "idle_seconds": None,
            "status": "gdbus not found",
        }
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return {
            "backend": "gnome",
            "ok": False,
            "idle_seconds": None,
            "status": "DBUS_SESSION_BUS_ADDRESS is empty",
            "command": gdbus,
        }
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
            stderr=subprocess.PIPE,
            text=True,
            timeout=0.6,
        )
    except subprocess.TimeoutExpired:
        return {
            "backend": "gnome",
            "ok": False,
            "idle_seconds": None,
            "status": "gdbus timeout",
            "command": gdbus,
        }
    except OSError as exc:
        return {
            "backend": "gnome",
            "ok": False,
            "idle_seconds": None,
            "status": f"gdbus error: {type(exc).__name__}: {exc}",
            "command": gdbus,
        }
    if result.returncode != 0:
        return {
            "backend": "gnome",
            "ok": False,
            "idle_seconds": None,
            "status": f"gdbus returned {result.returncode}",
            "stderr": result.stderr.strip(),
            "command": gdbus,
        }
    match = re.search(r"(\d+)", result.stdout)
    if not match:
        return {
            "backend": "gnome",
            "ok": False,
            "idle_seconds": None,
            "status": "gdbus output did not contain an idle value",
            "stdout": result.stdout.strip(),
            "command": gdbus,
        }
    return {
        "backend": "gnome",
        "ok": True,
        "idle_seconds": int(match.group(1)) / 1000.0,
        "status": "ok",
        "command": gdbus,
    }


def diagnose_xprintidle_idle() -> dict[str, Any]:
    xprintidle = shutil.which("xprintidle")
    if not xprintidle:
        return {
            "backend": "xprintidle",
            "ok": False,
            "idle_seconds": None,
            "status": "xprintidle not found",
        }
    if not os.environ.get("DISPLAY"):
        return {
            "backend": "xprintidle",
            "ok": False,
            "idle_seconds": None,
            "status": "DISPLAY is empty",
            "command": xprintidle,
        }
    try:
        result = subprocess.run(
            [xprintidle],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=0.4,
        )
    except subprocess.TimeoutExpired:
        return {
            "backend": "xprintidle",
            "ok": False,
            "idle_seconds": None,
            "status": "xprintidle timeout",
            "command": xprintidle,
        }
    except OSError as exc:
        return {
            "backend": "xprintidle",
            "ok": False,
            "idle_seconds": None,
            "status": f"xprintidle error: {type(exc).__name__}: {exc}",
            "command": xprintidle,
        }
    if result.returncode != 0:
        return {
            "backend": "xprintidle",
            "ok": False,
            "idle_seconds": None,
            "status": f"xprintidle returned {result.returncode}",
            "stderr": result.stderr.strip(),
            "command": xprintidle,
        }
    try:
        idle_seconds = int(result.stdout.strip()) / 1000.0
    except ValueError:
        return {
            "backend": "xprintidle",
            "ok": False,
            "idle_seconds": None,
            "status": "xprintidle output was not an integer",
            "stdout": result.stdout.strip(),
            "command": xprintidle,
        }
    return {
        "backend": "xprintidle",
        "ok": True,
        "idle_seconds": idle_seconds,
        "status": "ok",
        "command": xprintidle,
    }
