"""Message platform interfaces."""
from __future__ import annotations

from .base import MessagePlatform
from .display import prefer_movable_linux_platform, qt_platform_can_start
from .idle import idle_detection_diagnostics, system_idle_seconds
from .input_method import (
    configure_linux_input_method_environment,
    configure_qt_input_method_runtime,
    input_method_diagnostics,
    preferred_x11_display,
)
from .registry import available_message_platforms, create_message_platform
from .whatsapp import WhatsAppPlatform

__all__ = [
    "MessagePlatform",
    "WhatsAppPlatform",
    "available_message_platforms",
    "configure_linux_input_method_environment",
    "configure_qt_input_method_runtime",
    "create_message_platform",
    "idle_detection_diagnostics",
    "input_method_diagnostics",
    "prefer_movable_linux_platform",
    "preferred_x11_display",
    "qt_platform_can_start",
    "system_idle_seconds",
]
