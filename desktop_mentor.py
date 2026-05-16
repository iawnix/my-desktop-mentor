#!/usr/bin/env python3
"""My Desktop Mentor CLI entrypoint."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop_mentor_app.assets import DEFAULT_IMAGE, convert_image_to_ico, ensure_default_icon
from desktop_mentor_app.config_store import load_config, memory_path, save_config, todos_path
from desktop_mentor_app.constants import APP_NAME, DEFAULT_CLICK_MESSAGE
from desktop_mentor_app.stickers import discover_sticker_sets, sticker_frame_counts
from desktop_mentor_app.ui.dialogs import APP_STYLESHEET
from desktop_mentor_app.ui.pet_widget import DesktopMentorPet


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {APP_NAME}.")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE, help="PNG/JPG image for the desktop mentor")
    parser.add_argument("--message", default=DEFAULT_CLICK_MESSAGE, help="bubble text shown on touch/click")
    parser.add_argument("--size", type=int, default=150, help="portrait size in pixels")
    parser.add_argument("--quit-after", type=float, default=0.0, help="exit after N seconds")
    parser.add_argument("--self-test", action="store_true", help="load the app without opening a visible pet")
    parser.add_argument("--make-icon", nargs=2, metavar=("SOURCE_IMAGE", "OUTPUT_ICO"), help="convert a PNG/image file to ICO")
    parser.add_argument("--ensure-default-icon", action="store_true", help="generate assets/desktop_mentor.ico from the default mentor PNG")
    parser.add_argument("--force-icon", action="store_true", help="regenerate ICO even when the target is newer")
    parser.add_argument("--load-sticker-dir", type=Path, help="load action sticker frames from a directory with idle/tap/drag/... subfolders")
    return parser.parse_args(argv)


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

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(APP_STYLESHEET)
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
            "todo_repeat_seconds": pet.config.todo_repeat_seconds,
            "idle_mode": pet.config.idle_mode,
            "memory_enabled": pet.config.memory_enabled,
            "sticker_sets": pet.config.sticker_sets,
            "sticker_frame_counts": pet.sticker_frame_counts(),
            "current_action": pet.current_action,
            "memory_path": str(memory_path()),
            "todos_path": str(todos_path()),
            "icon": pet.config.icon_path,
            "icon_error": pet.icon_error,
            "window_size": [pet.width(), pet.height()],
            "config_path": str(pet.config_path),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    pet.show()
    if args.quit_after > 0:
        QTimer.singleShot(int(args.quit_after * 1000), app.quit)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
