"""Sticker frame loading and animation state."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap

from ..constants.stickers import STICKER_ACTION_IDLE, STICKER_ACTIONS, STICKER_ALPHA_THRESHOLD
from .animation import normalized_sticker_speed, sticker_frame_interval_seconds


class StickerAnimationManager:
    def __init__(self, base_pixmap: QPixmap) -> None:
        self.base_pixmap = base_pixmap
        self.frames: dict[str, list[QPixmap]] = {}
        self.source_rects: dict[str, QRectF] = {}
        self.content_rect_cache: dict[int, QRectF] = {}
        self.current_action = STICKER_ACTION_IDLE
        self.action_until = 0.0
        self.action_loop = True
        self.frame_index = 0
        self.last_frame_at = time.monotonic()

    def set_base_pixmap(self, pixmap: QPixmap) -> None:
        self.base_pixmap = pixmap
        self.content_rect_cache.clear()

    def reload(self, sticker_sets: dict[str, list[str]]) -> list[str]:
        frames: dict[str, list[QPixmap]] = {}
        invalid_paths: list[str] = []
        for action, paths in sticker_sets.items():
            loaded: list[QPixmap] = []
            for raw_path in paths:
                image_path = Path(raw_path).expanduser()
                pixmap = QPixmap(str(image_path))
                if pixmap.isNull():
                    invalid_paths.append(f"{action}: {raw_path}")
                    continue
                loaded.append(pixmap)
            if loaded:
                frames[action] = loaded
        self.frames = frames
        self.source_rects = {
            action: self.action_union_source_rect(loaded_frames)
            for action, loaded_frames in frames.items()
        }
        self.frame_index = 0
        self.last_frame_at = time.monotonic()
        return invalid_paths

    def has_multi_frame_action(self) -> bool:
        return any(len(items) > 1 for items in self.frames.values())

    def frame_counts(self) -> dict[str, int]:
        return {action: len(self.frames.get(action, [])) for action in STICKER_ACTIONS}

    def action_frames(self, action: str) -> list[QPixmap]:
        return self.frames.get(action) or self.frames.get(STICKER_ACTION_IDLE) or [self.base_pixmap]

    def current_pixmap(self) -> QPixmap:
        frames = self.action_frames(self.current_action)
        if not frames:
            return self.base_pixmap
        return frames[self.frame_index % len(frames)]

    def action_source_rect(self, action: str) -> QRectF:
        if action in self.frames:
            return QRectF(self.source_rects.get(action) or QRectF(self.action_frames(action)[0].rect()))
        if STICKER_ACTION_IDLE in self.frames:
            return QRectF(self.source_rects.get(STICKER_ACTION_IDLE) or QRectF(self.action_frames(STICKER_ACTION_IDLE)[0].rect()))
        return self.pixmap_content_rect(self.base_pixmap)

    def current_source_rect(self) -> QRectF:
        return self.action_source_rect(self.current_action)

    def action_union_source_rect(self, frames: list[QPixmap]) -> QRectF:
        union_rect = QRectF()
        for pixmap in frames:
            rect = self.pixmap_content_rect(pixmap)
            union_rect = QRectF(rect) if union_rect.isNull() else union_rect.united(rect)
        if union_rect.isNull() and frames:
            return QRectF(frames[0].rect())
        return union_rect

    def pixmap_content_rect(self, pixmap: QPixmap) -> QRectF:
        if pixmap.isNull():
            return QRectF()
        key = int(pixmap.cacheKey())
        cached = self.content_rect_cache.get(key)
        if cached is not None:
            return QRectF(cached)

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        width = image.width()
        height = image.height()
        if width <= 0 or height <= 0:
            rect = QRectF(pixmap.rect())
        else:
            rect = self._scan_content_rect(image, width, height, pixmap)
        self.content_rect_cache[key] = QRectF(rect)
        return rect

    def _scan_content_rect(self, image: QImage, width: int, height: int, pixmap: QPixmap) -> QRectF:
        scan_limit = 256
        if max(width, height) > scan_limit:
            ratio = scan_limit / max(width, height)
            scan_width = max(1, int(width * ratio))
            scan_height = max(1, int(height * ratio))
            scan_image = image.scaled(
                scan_width,
                scan_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            ).convertToFormat(QImage.Format.Format_RGBA8888)
        else:
            scan_image = image
            scan_width = width
            scan_height = height

        bits = scan_image.constBits()
        bytes_per_line = scan_image.bytesPerLine()
        left = scan_width
        right = -1
        top = scan_height
        bottom = -1
        for y in range(scan_height):
            alpha_row = bits[y * bytes_per_line + 3 : y * bytes_per_line + 3 + scan_width * 4 : 4]
            row_left = -1
            row_right = -1
            for x, alpha in enumerate(alpha_row):
                if alpha > STICKER_ALPHA_THRESHOLD:
                    if row_left < 0:
                        row_left = x
                    row_right = x
            if row_left >= 0:
                left = min(left, row_left)
                right = max(right, row_right)
                if top == scan_height:
                    top = y
                bottom = y
        if right < left or bottom < top:
            return QRectF(pixmap.rect())
        scale_x = width / max(1, scan_width)
        scale_y = height / max(1, scan_height)
        source_left = max(0, int(left * scale_x) - 2)
        source_top = max(0, int(top * scale_y) - 2)
        source_right = min(width, int((right + 1) * scale_x) + 2)
        source_bottom = min(height, int((bottom + 1) * scale_y) + 2)
        return QRectF(source_left, source_top, source_right - source_left, source_bottom - source_top)

    def animation_speed(self, value: object) -> float:
        return normalized_sticker_speed(value)

    def frame_interval_seconds(self, value: object) -> float:
        return sticker_frame_interval_seconds(value)

    def play_action(self, action: str, *, duration: float = 0.0, loop: bool = True, restart: bool = True) -> None:
        if action not in STICKER_ACTIONS:
            action = STICKER_ACTION_IDLE
        now = time.monotonic()
        if restart or action != self.current_action:
            self.frame_index = 0
            self.last_frame_at = now
        self.current_action = action
        self.action_loop = loop
        self.action_until = now + duration if duration > 0 else 0.0

    def update_active_action(self, now: float) -> None:
        if self.current_action != STICKER_ACTION_IDLE and self.action_until > 0 and now >= self.action_until:
            self.current_action = STICKER_ACTION_IDLE
            self.action_loop = True
            self.action_until = 0.0
            self.frame_index = 0
            self.last_frame_at = now

    def advance_frame(self, now: float, speed_value: object) -> None:
        frames = self.action_frames(self.current_action)
        if len(frames) <= 1:
            return
        interval = self.frame_interval_seconds(speed_value)
        elapsed = now - self.last_frame_at
        if elapsed < interval:
            return
        steps = max(1, int(elapsed / interval))
        if self.action_loop:
            self.frame_index = (self.frame_index + steps) % len(frames)
        else:
            self.frame_index = min(len(frames) - 1, self.frame_index + steps)
        self.last_frame_at += steps * interval

    def has_active_animation(self, now: float) -> bool:
        if len(self.action_frames(self.current_action)) > 1:
            return True
        return self.current_action != STICKER_ACTION_IDLE and (self.action_until <= 0 or now < self.action_until)
