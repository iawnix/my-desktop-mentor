"""Linux input-method setup for Qt text widgets."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


FCITX_PLUGIN_NAMES = (
    "libfcitx5platforminputcontextplugin.so",
    "libfcitxplatforminputcontextplugin.so",
)

KNOWN_QT_PLUGIN_ROOTS = (
    "/usr/lib/qt6/plugins",
    "/usr/lib64/qt6/plugins",
    "/usr/lib/x86_64-linux-gnu/qt6/plugins",
    "/usr/lib/aarch64-linux-gnu/qt6/plugins",
    "/usr/local/lib/qt6/plugins",
    "/usr/local/lib64/qt6/plugins",
    "/usr/lib/qt/plugins",
    "/usr/lib64/qt/plugins",
)


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def _truthy_env(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_path in paths:
        if not raw_path:
            continue
        path = str(Path(raw_path).expanduser())
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def configure_linux_session_bus() -> None:
    """Expose the user DBus session to Qt/fcitx when launched from ssh/systemd."""
    if not is_linux():
        return
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if not runtime_dir:
        candidate = Path("/run/user") / str(os.getuid())
        if candidate.is_dir():
            runtime_dir = str(candidate)
            os.environ["XDG_RUNTIME_DIR"] = runtime_dir
    if runtime_dir and not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        bus = Path(runtime_dir) / "bus"
        if bus.exists():
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"


def preferred_x11_display() -> str:
    """Return the most likely X11 display for this user when DISPLAY is absent."""
    if not is_linux():
        return ""
    socket_dir = Path("/tmp/.X11-unix")
    if not socket_dir.is_dir():
        return ""
    sockets = sorted(
        [path for path in socket_dir.glob("X*") if path.is_socket()],
        key=lambda path: int(path.name[1:]) if path.name[1:].isdigit() else 9999,
    )
    if not sockets:
        return ""
    uid = os.getuid()
    for socket in sockets:
        try:
            if socket.stat().st_uid == uid and socket.name[1:].isdigit():
                return f":{socket.name[1:]}"
        except OSError:
            continue
    first = sockets[0]
    return f":{first.name[1:]}" if first.name[1:].isdigit() else ""


def configure_linux_input_method_environment() -> None:
    """Set IM environment before QApplication is created."""
    if not is_linux():
        return
    requested = os.environ.get("DESKTOP_MENTOR_IM_MODULE", "").strip().lower()
    if requested in {"none", "off"}:
        return

    configure_linux_session_bus()
    module = requested
    if not module:
        qt_im = os.environ.get("QT_IM_MODULE", "").strip().lower()
        xmodifiers = os.environ.get("XMODIFIERS", "").strip().lower()
        if qt_im.startswith("fcitx") or "@im=fcitx" in xmodifiers:
            module = "fcitx"
        elif not qt_im and shutil.which("fcitx5") is not None:
            module = "fcitx"
        elif qt_im:
            module = qt_im

    force_module = bool(requested)
    if module in {"fcitx", "fcitx5"}:
        if force_module or not os.environ.get("QT_IM_MODULE") or os.environ.get("QT_IM_MODULE") == "fcitx5":
            os.environ["QT_IM_MODULE"] = "fcitx"
        if force_module or not os.environ.get("XMODIFIERS") or os.environ.get("XMODIFIERS") == "@im=fcitx5":
            os.environ["XMODIFIERS"] = "@im=fcitx"
        os.environ.setdefault("GTK_IM_MODULE", "fcitx")
        os.environ.setdefault("SDL_IM_MODULE", "fcitx")
        os.environ.setdefault("GLFW_IM_MODULE", "ibus")
    elif module:
        if force_module or not os.environ.get("QT_IM_MODULE"):
            os.environ["QT_IM_MODULE"] = module


def _qtpaths_plugin_roots() -> list[str]:
    roots: list[str] = []
    for command in ("qtpaths6", "qtpaths"):
        executable = shutil.which(command)
        if not executable:
            continue
        try:
            result = subprocess.run(
                [executable, "--plugin-dir"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.0,
            )
        except Exception:
            continue
        root = result.stdout.strip()
        if root:
            roots.append(root)
    return roots


def fcitx_qt_plugin_roots() -> list[str]:
    roots: list[str] = []
    candidates = [*_qtpaths_plugin_roots(), *KNOWN_QT_PLUGIN_ROOTS]
    for raw_root in candidates:
        root = Path(raw_root).expanduser()
        context_dir = root / "platforminputcontexts"
        if any((context_dir / name).is_file() for name in FCITX_PLUGIN_NAMES):
            roots.append(str(root))
    return _dedupe_paths(roots)


def fcitx_qt_plugin_files() -> list[str]:
    files: list[str] = []
    for root in fcitx_qt_plugin_roots():
        context_dir = Path(root) / "platforminputcontexts"
        for name in FCITX_PLUGIN_NAMES:
            path = context_dir / name
            if path.is_file():
                files.append(str(path))
    return _dedupe_paths(files)


def configure_qt_input_method_runtime() -> list[str]:
    """Append system Qt plugin roots that provide fcitx input contexts."""
    if not is_linux():
        return []
    if os.environ.get("QT_IM_MODULE", "").lower() not in {"fcitx", "fcitx5"}:
        return []

    from PySide6.QtCore import QCoreApplication, QLibraryInfo

    existing = list(QCoreApplication.libraryPaths())
    bundled = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    roots = _dedupe_paths([*existing, bundled, *fcitx_qt_plugin_roots()])
    if roots != existing:
        QCoreApplication.setLibraryPaths(roots)
    ensure_fcitx_running()
    return roots


def _fcitx_remote_name() -> str:
    remote = shutil.which("fcitx5-remote")
    if not remote:
        return ""
    try:
        result = subprocess.run(
            [remote, "-n"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.7,
        )
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def ensure_fcitx_running() -> None:
    if not is_linux():
        return
    if os.environ.get("QT_IM_MODULE", "").lower() not in {"fcitx", "fcitx5"}:
        return
    if not _truthy_env("DESKTOP_MENTOR_START_FCITX", True):
        return
    platform = os.environ.get("QT_QPA_PLATFORM", "").lower()
    if platform in {"offscreen", "minimal", "minimalegl"}:
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return
    if _fcitx_remote_name():
        return
    executable = shutil.which("fcitx5")
    if not executable:
        return
    try:
        subprocess.Popen(
            [executable, "-d"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(0.2)
    except Exception:
        return


def input_method_diagnostics() -> dict[str, object]:
    data: dict[str, object] = {
        "QT_IM_MODULE": os.environ.get("QT_IM_MODULE", ""),
        "XMODIFIERS": os.environ.get("XMODIFIERS", ""),
        "GTK_IM_MODULE": os.environ.get("GTK_IM_MODULE", ""),
        "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", ""),
        "DISPLAY": os.environ.get("DISPLAY", ""),
        "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
        "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
        "fcitx5": shutil.which("fcitx5") or "",
        "fcitx5_remote": _fcitx_remote_name(),
        "fcitx_qt_plugin_files": fcitx_qt_plugin_files(),
    }
    try:
        import PySide6
        from PySide6.QtCore import QCoreApplication, QLibraryInfo, qVersion

        data.update(
            {
                "PySide6": getattr(PySide6, "__version__", ""),
                "Qt": qVersion(),
                "qt_plugins_path": QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath),
                "qt_library_paths": list(QCoreApplication.libraryPaths()),
            }
        )
    except Exception as exc:
        data["qt_error"] = f"{type(exc).__name__}: {exc}"
    return data
