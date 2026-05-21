"""Display-platform selection helpers."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .input_method import preferred_x11_display


def qt_platform_can_start(platform: str, *, python_executable: str | None = None) -> bool:
    """Return whether a minimal QApplication can start on the requested Qt platform."""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = platform
    executable = python_executable or sys.executable
    try:
        result = subprocess.run(
            [
                executable,
                "-c",
                "from PySide6.QtWidgets import QApplication; app = QApplication([]); app.quit()",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def _x11_socket_available() -> bool:
    return Path("/tmp/.X11-unix/X0").exists() or Path("/tmp/.X11-unix/X1").exists()


def _configure_mutter_xauthority() -> None:
    if os.environ.get("XAUTHORITY"):
        return
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
    try:
        auth_files = sorted(runtime_dir.glob(".mutter-Xwaylandauth.*"))
    except OSError:
        return
    for auth_file in auth_files:
        if auth_file.is_file():
            os.environ["XAUTHORITY"] = str(auth_file)
            return


def prefer_movable_linux_platform() -> None:
    """Prefer XCB over Wayland when available so the pet can be moved reliably."""
    if not sys.platform.startswith("linux"):
        return
    if os.environ.get("DESKTOP_MENTOR_ALLOW_WAYLAND", "0") == "1":
        return
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "wayland":
        return

    _configure_mutter_xauthority()
    display = preferred_x11_display()
    if not os.environ.get("DISPLAY") and display:
        os.environ["DISPLAY"] = display
    if (os.environ.get("DISPLAY") or _x11_socket_available()) and qt_platform_can_start("xcb"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
