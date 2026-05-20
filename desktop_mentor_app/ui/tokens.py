"""UI-only layout and rendering parameters."""
from __future__ import annotations

FLUENT_FONT_STACK = '"SF Pro Text", "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif'

FLUENT_DARK_COLORS = {
    "accent": "#0080bd",
    "accent_hover": "#1099d6",
    "accent_pressed": "#006494",
    "accent_soft": "#083a55",
    "accent_border": "#1a7eaf",
    "canvas": "#181818",
    "danger": "#442726",
    "danger_border": "#8a4a47",
    "danger_border_hover": "#c75c58",
    "danger_hover": "#5a2f2e",
    "divider": "#2e2e2e",
    "empty_border": "#505050",
    "focus": "#6fcbf3",
    "info_border": "#337fa8",
    "info_surface": "#0b3248",
    "info_text": "#dff6ff",
    "input": "#2e2e2e",
    "input_focus": "#282828",
    "menu": "#282828",
    "plan_border": "#4c6f87",
    "plan_surface": "#1d2429",
    "scroll": "#555555",
    "scroll_hover": "#6f6f6f",
    "surface_window": "#181818",
    "surface_panel": "#212121",
    "surface_card": "#212121",
    "surface_control": "#282828",
    "surface_hover": "#303030",
    "surface_pressed": "#1f1f1f",
    "surface_sidebar": "#151515",
    "surface_translucent": "#1f1f1f",
    "border": "#2e2e2e",
    "border_card": "#303030",
    "border_control": "#3a3a3a",
    "border_hover": "#5a5a5a",
    "close_hover": "#c42b1c",
    "state_success": "#40c977",
    "state_warning": "#ffd240",
    "tool_explore": "#8f8f8f",
    "tool_run": "#6fcbf3",
    "tool_edit": "#ffc300",
    "tool_ask": "#05bdf5",
    "text_primary": "#f3f3f3",
    "text_on_accent": "#ffffff",
    "text_secondary": "#c9c9c9",
    "text_muted": "#a7a7a7",
    "text_subtle": "#8f8f8f",
    "text_disabled": "#777777",
    "disabled": "#282828",
    "disabled_border": "#3a3a3a",
}

FLUENT_RADII = {
    "dialog": 12,
    "surface": 8,
    "control": 8,
    "checkbox": 5,
    "tooltip": 6,
}

FLUENT_METRICS = {
    "title_close_size": 28,
    "resize_grip_size": 18,
    "scrollbar_width": 10,
}

BUBBLE_MIN_HEIGHT = 88
BUBBLE_TOP = 7
BUBBLE_TAIL_HEIGHT = 16
BUBBLE_BOTTOM_PAD = 9
BUBBLE_MIN_WIDTH = 202
BUBBLE_MAX_WIDTH = 420
BUBBLE_BODY_MIN_HEIGHT = 56
BUBBLE_BODY_MAX_HEIGHT = 320
BUBBLE_TEXT_PAD_X = 12
BUBBLE_TEXT_PAD_Y = 10
MAX_BUBBLE_TEXT_CHARS = 520

CHAT_BUTTON_MIN_SIZE = 30
CHAT_BUTTON_MAX_SIZE = 44
ACTION_BUTTON_MIN_SIZE = 32
ACTION_BUTTON_MAX_SIZE = 42
ACTION_BUTTON_GAP = 8
ACTION_BUTTON_STICKER_GAP = 9
ACTION_BUTTON_OUTER_PAD = 8

DROP_HOTZONE_PAD = 30
DROP_EFFECT_DURATION = 0.9
DRAG_RELEASE_EFFECT_DURATION = 0.22
CHAT_BUTTON_MARGIN = 4
WINDOW_PAD = 15

TODO_BUBBLE_MAX_VISIBLE = 6
TODO_BUBBLE_GAP = 8
TODO_BUBBLE_TOP = 7
TODO_BUBBLE_MIN_WIDTH = 220
TODO_BUBBLE_MAX_WIDTH = 390
TODO_BUBBLE_TEXT_PAD_X = 12
TODO_BUBBLE_TEXT_PAD_Y = 9
TODO_BUBBLE_MIN_HEIGHT = 50
TODO_BUBBLE_MAX_HEIGHT = 96

FULLSCREEN_ALERT_DURATION_MS = 4_200
