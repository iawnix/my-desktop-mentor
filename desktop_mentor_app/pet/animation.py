"""Sticker animation domain helpers."""
from __future__ import annotations

from ..constants import (
    DEFAULT_STICKER_ANIMATION_SPEED,
    MAX_STICKER_ANIMATION_SPEED,
    MIN_STICKER_ANIMATION_SPEED,
    STICKER_FRAME_INTERVAL_MS,
)


def normalized_sticker_speed(value: object) -> float:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        speed = DEFAULT_STICKER_ANIMATION_SPEED
    return max(MIN_STICKER_ANIMATION_SPEED, min(MAX_STICKER_ANIMATION_SPEED, speed))


def sticker_frame_interval_seconds(value: object) -> float:
    return (STICKER_FRAME_INTERVAL_MS / 1000) / normalized_sticker_speed(value)
