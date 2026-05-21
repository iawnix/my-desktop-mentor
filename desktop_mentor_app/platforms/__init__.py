"""Message platform interfaces."""
from __future__ import annotations

from .base import MessagePlatform
from .display import prefer_movable_linux_platform, qt_platform_can_start
from .registry import available_message_platforms, create_message_platform
from .whatsapp import WhatsAppPlatform

__all__ = [
    "MessagePlatform",
    "WhatsAppPlatform",
    "available_message_platforms",
    "create_message_platform",
    "prefer_movable_linux_platform",
    "qt_platform_can_start",
]
