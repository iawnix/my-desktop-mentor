"""Shared constants for My Desktop Mentor."""
from __future__ import annotations

APP_NAME = "我的桌面导师"
APP_ID = "my-desktop-mentor"
DEFAULT_MODEL = "gpt-4o-mini"
CONFIG_POINTER_NAME = "config-dir.txt"
DEFAULT_PET_SIZE = 220
MIN_PET_SIZE = 72
MAX_PET_SIZE = 560

DEFAULT_CLICK_MESSAGE = "我在。把目标和卡点说清楚，我们先找下一步。"
DEFAULT_IDLE_MESSAGE = "进展怎么样？需要我帮你梳理一下下一步吗？"
DEFAULT_DROP_MESSAGE = "文件我收到了。先看目标、约束和你最想解决的问题。"

STICKER_ACTION_IDLE = "idle"
STICKER_ACTION_TAP = "tap"
STICKER_ACTION_DRAG = "drag"
STICKER_ACTION_THINKING = "thinking"
STICKER_ACTION_SPEAKING = "speaking"
STICKER_ACTION_ALERT = "alert"
STICKER_ACTION_DROP_FILE = "drop_file"
STICKER_ACTION_ERROR = "error"
STICKER_ACTIONS = (
    STICKER_ACTION_IDLE,
    STICKER_ACTION_TAP,
    STICKER_ACTION_DRAG,
    STICKER_ACTION_THINKING,
    STICKER_ACTION_SPEAKING,
    STICKER_ACTION_ALERT,
    STICKER_ACTION_DROP_FILE,
    STICKER_ACTION_ERROR,
)
STICKER_ACTION_LABELS = {
    STICKER_ACTION_IDLE: "待机 idle",
    STICKER_ACTION_TAP: "点击 tap",
    STICKER_ACTION_DRAG: "拖动 drag",
    STICKER_ACTION_THINKING: "思考 thinking",
    STICKER_ACTION_SPEAKING: "说话 speaking",
    STICKER_ACTION_ALERT: "提醒 alert",
    STICKER_ACTION_DROP_FILE: "拖入文件 drop_file",
    STICKER_ACTION_ERROR: "错误 error",
}
MAX_STICKER_FRAMES = 64
STICKER_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
STICKER_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
MAX_AGENT_REPLY_CHARS = 520

TODO_CHECK_INTERVAL_MS = 1_000
DEFAULT_TODO_REPEAT_SECONDS = 300
MIN_TODO_REPEAT_SECONDS = 10
MAX_TODO_REPEAT_SECONDS = 86_400
DEFAULT_MESSAGE_SECONDS = 3.2
MIN_MESSAGE_SECONDS = 0.8
MAX_MESSAGE_SECONDS = 60.0
DEFAULT_MEMORY_ENABLED = False
DEFAULT_MEMORY_TURNS = 8
MAX_MEMORY_TURNS = 24
MIN_IDLE_SECONDS = 30
MAX_IDLE_SECONDS = 86_400
DEFAULT_IDLE_SECONDS = 30
IDLE_CHECK_INTERVAL_MS = 5_000
IDLE_MODE_LIGHT = "light"
IDLE_MODE_FULLSCREEN = "fullscreen"
DEFAULT_IDLE_MODE = IDLE_MODE_LIGHT
IDLE_MODE_OPTIONS = (
    (IDLE_MODE_LIGHT, "轻量气泡"),
    (IDLE_MODE_FULLSCREEN, "满屏提醒"),
)

DEFAULT_PERSONALITY_PROMPT = """你是桌面宠物 agent「我的桌面导师」，默认形象是一位对学生友好、清晰、可靠的科研导师。

沟通风格：
- 先理解学生的目标和当前卡点，再给出可执行的下一步。
- 语气温和直接，不羞辱、不PUA、不制造无意义压力。
- 对科研问题，帮助拆分为：问题定义、已有证据、关键风险、下一步实验或写作动作。
- 对日常任务，回复要短，优先给具体行动建议。
- 长期没有互动时，用配置里的 idle 提醒话术轻量询问进展。

输出要求：
- 默认每次不超过 3 句话。
- 可以鼓励进度，但不要替用户夸大成果。
- 不知道时直接说明，并建议如何补充信息。
"""
