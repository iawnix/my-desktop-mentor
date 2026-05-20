#!/usr/bin/env python3
"""My Desktop Mentor CLI entrypoint."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from desktop_mentor_app.input_method import (
    configure_linux_input_method_environment,
    configure_qt_input_method_runtime,
    input_method_diagnostics,
    preferred_x11_display,
)

configure_linux_input_method_environment()

from PySide6.QtWidgets import QApplication

from desktop_mentor_app.assets import DEFAULT_IMAGE, convert_image_to_ico, ensure_default_icon
from desktop_mentor_app.config_store import chat_history_path, load_config, memory_path, save_config, todos_path
from desktop_mentor_app.control.audit_log import audit_log_path
from desktop_mentor_app.core.runtime import run_qt_app
from desktop_mentor_app.constants import APP_NAME, DEFAULT_CLICK_MESSAGE, DEFAULT_PET_SIZE
from desktop_mentor_app.idle_detector import idle_detection_diagnostics
from desktop_mentor_app.logging_config import app_log_path, configure_logging
from desktop_mentor_app.stickers import discover_sticker_sets, sticker_frame_counts
from desktop_mentor_app.ui.theme import apply_app_theme
from desktop_mentor_app.ui.pet_widget import DesktopMentorPet


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {APP_NAME}.")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE, help="PNG/JPG image for the desktop mentor")
    parser.add_argument("--message", default=DEFAULT_CLICK_MESSAGE, help="bubble text shown on touch/click")
    parser.add_argument("--size", type=int, default=DEFAULT_PET_SIZE, help="portrait size in pixels")
    parser.add_argument("--quit-after", type=float, default=0.0, help="exit after N seconds")
    parser.add_argument("--self-test", action="store_true", help="load the app without opening a visible pet")
    parser.add_argument("--diagnose", action="store_true", help="print Linux display/input-method diagnostics")
    parser.add_argument("--make-icon", nargs=2, metavar=("SOURCE_IMAGE", "OUTPUT_ICO"), help="convert a PNG/image file to ICO")
    parser.add_argument("--ensure-default-icon", action="store_true", help="generate assets/desktop_mentor.ico from the default mentor PNG")
    parser.add_argument("--force-icon", action="store_true", help="regenerate ICO even when the target is newer")
    parser.add_argument("--load-sticker-dir", type=Path, help="load action sticker frames from a directory with idle/tap/drag/... subfolders")
    return parser.parse_args(argv)

def prefer_movable_linux_platform() -> None:
    if not sys.platform.startswith("linux"):
        return
    if os.environ.get("DESKTOP_MENTOR_ALLOW_WAYLAND", "0") == "1":
        return
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "wayland":
        return

    if not os.environ.get("XAUTHORITY"):
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
        for auth_file in runtime_dir.glob(".mutter-Xwaylandauth.*"):
            if auth_file.is_file():
                os.environ["XAUTHORITY"] = str(auth_file)
                break

    display = preferred_x11_display()
    if not os.environ.get("DISPLAY") and display:
        os.environ["DISPLAY"] = display
    if (
        os.environ.get("DISPLAY") or Path("/tmp/.X11-unix/X0").exists() or Path("/tmp/.X11-unix/X1").exists()
    ) and qt_platform_can_start("xcb"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def qt_platform_can_start(platform: str) -> bool:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = platform
    try:
        result = subprocess.run(
            [
                sys.executable,
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


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.make_icon:
        icon_path = convert_image_to_ico(Path(args.make_icon[0]), Path(args.make_icon[1]), force=True)
        print(json.dumps({"ok": True, "icon": str(icon_path)}, ensure_ascii=False))
        return 0
    if args.ensure_default_icon:
        icon_path = ensure_default_icon(force=args.force_icon)
        print(json.dumps({"ok": True, "icon": str(icon_path), "source": str(DEFAULT_IMAGE)}, ensure_ascii=False))
        return 0
    if args.load_sticker_dir:
        sticker_sets = discover_sticker_sets(args.load_sticker_dir)
        if not sticker_sets:
            print(json.dumps({"ok": False, "error": f"no sticker frames found in {args.load_sticker_dir}"}, ensure_ascii=False))
            return 1
        config = load_config()
        config.sticker_sets = sticker_sets
        path = save_config(config)
        print(
            json.dumps(
                {
                    "ok": True,
                    "config_path": str(path),
                    "sticker_dir": str(args.load_sticker_dir.expanduser().resolve()),
                    "frame_counts": sticker_frame_counts(sticker_sets),
                },
                ensure_ascii=False,
            )
        )
        return 0

    configure_linux_input_method_environment()
    prefer_movable_linux_platform()
    configure_qt_input_method_runtime()
    configure_logging(debug=os.environ.get("DESKTOP_MENTOR_DEBUG", "").lower() in {"1", "true", "yes", "on"})
    if args.diagnose:
        print(
            json.dumps(
                {
                    "input_method": input_method_diagnostics(),
                    "idle_detection": idle_detection_diagnostics(),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    apply_app_theme(app)
    image_path = args.image.expanduser().resolve()
    pet = DesktopMentorPet(image_path, args.message, args.size)

    if args.self_test:
        result = {
            "ok": True,
            "image": str(pet.image_path),
            "image_size": [pet.pixmap.width(), pet.pixmap.height()],
            "click_message": pet.config.click_message,
            "idle_message": pet.config.idle_message,
            "drop_message": pet.config.drop_message,
            "message_seconds": pet.config.message_seconds,
            "sticker_animation_speed": pet.config.sticker_animation_speed,
            "todo_repeat_seconds": pet.config.todo_repeat_seconds,
            "idle_mode": pet.config.idle_mode,
            "memory_enabled": pet.config.memory_enabled,
            "control_enabled": pet.config.control_enabled,
            "control_workspace": pet.config.control_workspace,
            "control_audit_path": str(audit_log_path()),
            "chat_history_path": str(chat_history_path()),
            "sticker_sets": pet.config.sticker_sets,
            "sticker_frame_counts": pet.sticker_frame_counts(),
            "current_action": pet.current_action,
            "memory_path": str(memory_path()),
            "todos_path": str(todos_path()),
            "icon": pet.config.icon_path,
            "icon_error": pet.icon_error,
            "window_size": [pet.width(), pet.height()],
            "config_path": str(pet.config_path),
            "config_schema_version": pet.config.schema_version,
            "app_log_path": str(app_log_path(pet.config_path)),
            "quit_on_last_window_closed": app.quitOnLastWindowClosed(),
            "idle_detection": idle_detection_diagnostics(),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    return run_qt_app(app, lambda: pet, quit_after=args.quit_after)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
