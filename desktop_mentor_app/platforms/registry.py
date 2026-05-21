"""Message-platform factory registry."""
from __future__ import annotations

from collections.abc import Callable

from .base import MessagePlatform
from .whatsapp import WhatsAppPlatform

PlatformFactory = Callable[[], MessagePlatform]

_PLATFORM_FACTORIES: dict[str, PlatformFactory] = {
    WhatsAppPlatform.name: WhatsAppPlatform,
}


def available_message_platforms() -> tuple[str, ...]:
    return tuple(sorted(_PLATFORM_FACTORIES))


def create_message_platform(name: str) -> MessagePlatform:
    platform_name = str(name or "").strip().lower()
    try:
        factory = _PLATFORM_FACTORIES[platform_name]
    except KeyError as exc:
        raise ValueError(f"unsupported message platform: {name}") from exc
    return factory()
