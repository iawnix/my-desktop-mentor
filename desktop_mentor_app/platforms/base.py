"""External message platform protocol."""
from __future__ import annotations

from typing import Protocol


class MessagePlatform(Protocol):
    name: str

    async def send_message(self, target: str, text: str) -> None:
        """Send a message to an external platform target."""
