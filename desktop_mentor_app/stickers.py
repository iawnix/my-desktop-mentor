"""Compatibility exports for action sticker set helpers.

New code should import from ``desktop_mentor_app.pet.stickers``.
"""
from __future__ import annotations

from .pet.stickers import discover_sticker_sets, normalize_sticker_sets, sticker_frame_counts

__all__ = ["discover_sticker_sets", "normalize_sticker_sets", "sticker_frame_counts"]
