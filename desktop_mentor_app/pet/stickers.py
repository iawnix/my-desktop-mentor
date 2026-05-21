"""Action sticker set helpers."""
from __future__ import annotations

from pathlib import Path

from ..constants.stickers import MAX_STICKER_FRAMES, STICKER_ACTIONS, STICKER_IMAGE_SUFFIXES


def normalize_sticker_sets(value: object) -> dict[str, list[str]]:
    """Return ordered image lists keyed by known action."""
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for action in STICKER_ACTIONS:
        raw_items = value.get(action, [])
        if isinstance(raw_items, str):
            candidates: object = raw_items.replace(";", "\n").splitlines()
        elif isinstance(raw_items, (list, tuple)):
            candidates = raw_items
        else:
            continue

        paths: list[str] = []
        for item in candidates:
            text = str(item).strip().strip("\"'")
            if not text:
                continue
            paths.append(text)
            if len(paths) >= MAX_STICKER_FRAMES:
                break
        if paths:
            normalized[action] = paths
    return normalized


def sticker_frame_counts(sticker_sets: dict[str, list[str]]) -> dict[str, int]:
    return {action: len(sticker_sets.get(action, [])) for action in STICKER_ACTIONS}


def discover_sticker_sets(root_dir: Path) -> dict[str, list[str]]:
    root = root_dir.expanduser().resolve()
    discovered: dict[str, list[str]] = {}
    for action in STICKER_ACTIONS:
        action_dir = root / action
        if not action_dir.is_dir():
            continue
        paths = [
            path
            for path in sorted(action_dir.iterdir())
            if path.is_file() and path.suffix.lower() in STICKER_IMAGE_SUFFIXES
        ]
        if paths:
            discovered[action] = [str(path) for path in paths[:MAX_STICKER_FRAMES]]
    return discovered
