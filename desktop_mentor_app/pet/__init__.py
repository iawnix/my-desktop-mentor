"""Pet domain managers and animation helpers."""
from __future__ import annotations

__all__ = [
    "PetConversationService",
    "PetTodoService",
    "StickerAnimationManager",
    "sticker_frame_interval_seconds",
]


def __getattr__(name: str):
    if name == "sticker_frame_interval_seconds":
        from .animation import sticker_frame_interval_seconds

        return sticker_frame_interval_seconds
    if name == "PetConversationService":
        from .chat_manager import PetConversationService

        return PetConversationService
    if name == "StickerAnimationManager":
        from .sticker_manager import StickerAnimationManager

        return StickerAnimationManager
    if name == "PetTodoService":
        from .todo_manager import PetTodoService

        return PetTodoService
    raise AttributeError(name)
