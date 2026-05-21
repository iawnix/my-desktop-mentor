from __future__ import annotations

import os
import unittest
from unittest import mock

from desktop_mentor_app.platforms import display


class DisplayPlatformTests(unittest.TestCase):
    def test_non_wayland_platform_does_not_probe_xcb(self) -> None:
        original_platform = display.sys.platform
        old_env = os.environ.copy()
        try:
            display.sys.platform = "linux"
            os.environ.clear()
            os.environ["QT_QPA_PLATFORM"] = "xcb"
            with mock.patch.object(display, "qt_platform_can_start") as can_start:
                display.prefer_movable_linux_platform()
            can_start.assert_not_called()
        finally:
            display.sys.platform = original_platform
            os.environ.clear()
            os.environ.update(old_env)

    def test_wayland_can_be_explicitly_allowed(self) -> None:
        original_platform = display.sys.platform
        old_env = os.environ.copy()
        try:
            display.sys.platform = "linux"
            os.environ.clear()
            os.environ["QT_QPA_PLATFORM"] = "wayland"
            os.environ["DESKTOP_MENTOR_ALLOW_WAYLAND"] = "1"
            with mock.patch.object(display, "qt_platform_can_start") as can_start:
                display.prefer_movable_linux_platform()
            can_start.assert_not_called()
            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "wayland")
        finally:
            display.sys.platform = original_platform
            os.environ.clear()
            os.environ.update(old_env)


if __name__ == "__main__":
    unittest.main()
