"""Message platform interfaces."""
from __future__ import annotations

from .base import MessagePlatform
from .whatsapp import WhatsAppPlatform

__all__ = ["MessagePlatform", "WhatsAppPlatform"]
