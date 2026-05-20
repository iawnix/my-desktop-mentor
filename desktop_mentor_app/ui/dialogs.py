"""Compatibility exports for dialog widgets.

New code should import concrete widgets from their focused modules.
"""
from __future__ import annotations

from .chat_components import (
    ChatInputEdit,
    ChatMessageCard,
    TextMarkdownMessageView,
    create_markdown_message_view,
    webengine_markdown_enabled,
)
from .chat_dialog import ChatDialog
from .dialog_chrome import (
    DialogTitleBar,
    activate_input_window,
    add_resize_grip,
    enable_text_input,
    make_hairline,
    make_transparent,
    mark_button,
    modern_form_layout,
    prepare_modern_menu,
    restyle,
    section_card,
    setup_modern_dialog,
    style_dialog_buttons,
    styled_label,
    title_bar,
    transparent_frame,
    transparent_scroll_area,
)
from .idle_alert import FullScreenIdleAlert
from .settings_dialog import SettingsDialog
from .sticker_set_editor import StickerSetEditor
from .text_view_dialog import TextViewDialog
from .todo_dialog import TodoDialog

__all__ = [
    "ChatDialog",
    "ChatInputEdit",
    "ChatMessageCard",
    "DialogTitleBar",
    "FullScreenIdleAlert",
    "SettingsDialog",
    "StickerSetEditor",
    "TextMarkdownMessageView",
    "TextViewDialog",
    "TodoDialog",
    "activate_input_window",
    "add_resize_grip",
    "create_markdown_message_view",
    "enable_text_input",
    "make_hairline",
    "make_transparent",
    "mark_button",
    "modern_form_layout",
    "prepare_modern_menu",
    "restyle",
    "section_card",
    "setup_modern_dialog",
    "style_dialog_buttons",
    "styled_label",
    "title_bar",
    "transparent_frame",
    "transparent_scroll_area",
    "webengine_markdown_enabled",
]
