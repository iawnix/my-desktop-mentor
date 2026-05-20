"""WhatsApp platform placeholder."""
from __future__ import annotations


class WhatsAppPlatform:
    name = "whatsapp"

    async def send_message(self, target: str, text: str) -> None:
        raise NotImplementedError("WhatsApp integration is intentionally not connected yet.")
