"""Linux input-method setup for Qt text widgets."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


FCITX_PLUGIN_NAMES = (
    "libfcitx5platforminputcontextplugin.so",
    "libfcitxplatforminputcontextplugin.so",
    "libfcitxplatforminputcontextplugin-qt6.so",
    "libfcitx5platforminputcontextplugin-qt6.so",
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


def _dedupe_files(paths: list[Path]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        try:
            normalized = str(path.expanduser().resolve(strict=False))
        except OSError:
            normalized = str(path.expanduser())
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _platform_input_context_files(plugin_root: str) -> list[str]:
    context_dir = Path(plugin_root).expanduser() / "platforminputcontexts"
    if not context_dir.is_dir():
        return []
    return _dedupe_files(sorted(path for path in context_dir.glob("*.so") if path.is_file()))


def _fcitx_plugin_files_in_root(plugin_root: str) -> list[str]:
    context_dir = Path(plugin_root).expanduser() / "platforminputcontexts"
    if not context_dir.is_dir():
        return []
    return _dedupe_files([context_dir / name for name in FCITX_PLUGIN_NAMES if (context_dir / name).is_file()])


def _qt_version_tuple(version: str) -> tuple[int, int, int] | None:
    parts = version.split(".")
    if len(parts) < 2:
        return None
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    return major, minor, patch


def _plugin_qt_abi_versions(plugin_file: str) -> list[str]:
    """Read Qt symbol versions from a plugin binary without loading it."""
    path = Path(plugin_file)
    if not path.is_file():
        return []
    commands = []
    if shutil.which("strings"):
        commands.append(["strings", "-a", str(path)])
    if shutil.which("objdump"):
        commands.append(["objdump", "-T", str(path)])
    matches: set[tuple[int, int]] = set()
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.5,
            )
        except Exception:
            continue
        for major, minor in re.findall(r"Qt_([0-9]+)\.([0-9]+)", result.stdout):
            try:
                matches.add((int(major), int(minor)))
            except ValueError:
                continue
        if matches:
            break
    return [f"{major}.{minor}" for major, minor in sorted(matches)]


def _plugin_compatibility(plugin_file: str, runtime_qt_version: str) -> dict[str, object]:
    runtime = _qt_version_tuple(runtime_qt_version)
    abi_versions = _plugin_qt_abi_versions(plugin_file)
    result: dict[str, object] = {
        "path": plugin_file,
        "qt_abi_versions": abi_versions,
        "compatible": None,
        "exact_minor_match": False,
    }
    if runtime is None or not abi_versions:
        return result
    runtime_major, runtime_minor, _runtime_patch = runtime
    parsed: list[tuple[int, int]] = []
    for version in abi_versions:
        major_minor = _qt_version_tuple(version)
        if major_minor is not None:
            parsed.append((major_minor[0], major_minor[1]))
    if not parsed:
        return result
    result["exact_minor_match"] = any(major == runtime_major and minor == runtime_minor for major, minor in parsed)
    result["compatible"] = all(major == runtime_major and minor <= runtime_minor for major, minor in parsed)
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
        if _fcitx_plugin_files_in_root(str(root)):
            roots.append(str(root))
    return _dedupe_paths(roots)


def fcitx_qt_plugin_files() -> list[str]:
    files: list[str] = []
    for root in fcitx_qt_plugin_roots():
        files.extend(_fcitx_plugin_files_in_root(root))
    return _dedupe_paths(files)


def compatible_fcitx_qt_plugin_roots(runtime_qt_version: str) -> list[str]:
    compatible: list[str] = []
    unknown: list[str] = []
    for root in fcitx_qt_plugin_roots():
        root_files = _fcitx_plugin_files_in_root(root)
        if not root_files:
            continue
        plugin_states = [_plugin_compatibility(path, runtime_qt_version).get("compatible") for path in root_files]
        if any(state is True for state in plugin_states):
            compatible.append(root)
        elif any(state is None for state in plugin_states):
            unknown.append(root)
    if compatible:
        return _dedupe_paths(compatible)
    return _dedupe_paths(unknown)


def configure_qt_input_method_runtime() -> list[str]:
    """Append system Qt plugin roots that provide fcitx input contexts."""
    if not is_linux():
        return []
    if os.environ.get("QT_IM_MODULE", "").lower() not in {"fcitx", "fcitx5"}:
        return []

    from PySide6.QtCore import QCoreApplication, QLibraryInfo, qVersion

    existing = list(QCoreApplication.libraryPaths())
    bundled = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    roots = _dedupe_paths([*existing, bundled, *compatible_fcitx_qt_plugin_roots(qVersion())])
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

        qt_plugins_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        qt_library_paths = list(QCoreApplication.libraryPaths())
        fcitx_files = fcitx_qt_plugin_files()
        bundled_fcitx = _fcitx_plugin_files_in_root(qt_plugins_path)
        compatibility = [_plugin_compatibility(path, qVersion()) for path in fcitx_files]
        data.update(
            {
                "PySide6": getattr(PySide6, "__version__", ""),
                "Qt": qVersion(),
                "qt_plugins_path": qt_plugins_path,
                "qt_platforminputcontext_files": _platform_input_context_files(qt_plugins_path),
                "qt_bundled_fcitx_plugin_files": bundled_fcitx,
                "fcitx_qt_plugin_roots": fcitx_qt_plugin_roots(),
                "compatible_fcitx_qt_plugin_roots": compatible_fcitx_qt_plugin_roots(qVersion()),
                "fcitx_plugin_compatibility": compatibility,
                "fcitx_runtime_has_compatible_plugin": any(item.get("compatible") is True for item in compatibility),
                "qt_library_paths": qt_library_paths,
            }
        )
    except Exception as exc:
        data["qt_error"] = f"{type(exc).__name__}: {exc}"
    return data
