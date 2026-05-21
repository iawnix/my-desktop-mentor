from __future__ import annotations

import unittest

from desktop_mentor_app.constants.stickers import (
    DEFAULT_STICKER_ANIMATION_SPEED,
    MAX_STICKER_ANIMATION_SPEED,
    MIN_STICKER_ANIMATION_SPEED,
    STICKER_FRAME_INTERVAL_MS,
)
from desktop_mentor_app.pet.animation import normalized_sticker_speed, sticker_frame_interval_seconds


class StickerAnimationTests(unittest.TestCase):
    def test_speed_is_clamped_to_supported_range(self) -> None:
        self.assertEqual(normalized_sticker_speed(0), MIN_STICKER_ANIMATION_SPEED)
        self.assertEqual(normalized_sticker_speed(99), MAX_STICKER_ANIMATION_SPEED)
        self.assertEqual(normalized_sticker_speed("bad"), DEFAULT_STICKER_ANIMATION_SPEED)

    def test_frame_interval_uses_configured_speed(self) -> None:
        self.assertAlmostEqual(
            sticker_frame_interval_seconds(2.0),
            (STICKER_FRAME_INTERVAL_MS / 1000) / 2.0,
        )


if __name__ == "__main__":
    unittest.main()
