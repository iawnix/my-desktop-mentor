from __future__ import annotations

import unittest

from desktop_mentor_app.platforms import (
    MessagePlatform,
    WhatsAppPlatform,
    available_message_platforms,
    create_message_platform,
)


class MessagePlatformTests(unittest.IsolatedAsyncioTestCase):
    def test_only_whatsapp_platform_is_registered(self) -> None:
        self.assertEqual(available_message_platforms(), ("whatsapp",))

    def test_create_whatsapp_platform(self) -> None:
        platform = create_message_platform(" WhatsApp ")

        self.assertIsInstance(platform, WhatsAppPlatform)
        self.assertIsInstance(platform, MessagePlatform)
        self.assertEqual(platform.name, "whatsapp")

    def test_unknown_platform_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            create_message_platform("telegram")

    async def test_whatsapp_platform_is_placeholder(self) -> None:
        platform = create_message_platform("whatsapp")

        with self.assertRaises(NotImplementedError):
            await platform.send_message("+15550000000", "hello")


if __name__ == "__main__":
    unittest.main()
