"""Compatibility exports for bundled resource helpers.

New code should import from ``desktop_mentor_app.core.assets``.
"""
from __future__ import annotations

from .core.assets import (
    DEFAULT_ICON,
    DEFAULT_IMAGE,
    DEFAULT_STICKERS_DIR,
    ROOT,
    TODO_BADGE_IMAGE,
    app_root,
    centered_icon_layer,
    convert_image_to_ico,
    ensure_default_icon,
    file_digest,
    icon_cache_path_for_image,
    qimage_png_bytes,
    safe_stem,
    write_ico,
)

__all__ = [
    "DEFAULT_ICON",
    "DEFAULT_IMAGE",
    "DEFAULT_STICKERS_DIR",
    "ROOT",
    "TODO_BADGE_IMAGE",
    "app_root",
    "centered_icon_layer",
    "convert_image_to_ico",
    "ensure_default_icon",
    "file_digest",
    "icon_cache_path_for_image",
    "qimage_png_bytes",
    "safe_stem",
    "write_ico",
]
