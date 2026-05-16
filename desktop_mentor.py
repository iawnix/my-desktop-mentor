#!/usr/bin/env python3
"""My Desktop Mentor.

A small always-on-top desktop sticker using the supplied portrait image.
Tap/click the mentor to show the configured message; drag to move.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QDateTime, QIODevice, QObject, QPoint, QPointF, QRect, QRectF, QTimer, Qt, QEvent, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QComboBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


APP_STYLESHEET = """
QDialog {
    background: #111827;
    color: #e5e7eb;
    font-size: 13px;
}
QLabel {
    color: #d1d5db;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox, QListWidget {
    background: #0b1220;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #f8fafc;
    padding: 8px 10px;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus, QListWidget:focus {
    border-color: #60a5fa;
}
QTextEdit {
    padding: 10px;
}
QPushButton {
    background: #1f2937;
    border: 1px solid #3b4758;
    border-radius: 8px;
    color: #f8fafc;
    padding: 8px 14px;
}
QPushButton:hover {
    background: #263449;
    border-color: #60a5fa;
}
QPushButton:pressed {
    background: #1d4ed8;
}
QDialogButtonBox QPushButton {
    min-width: 76px;
}
QComboBox::drop-down {
    border: 0;
    width: 24px;
}
QMenu {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    color: #e5e7eb;
    padding: 8px;
}
QMenu::item {
    border-radius: 7px;
    padding: 8px 28px 8px 12px;
}
QMenu::item:selected {
    background: #2563eb;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #263244;
    margin: 6px 8px;
}
"""


def app_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parent


ROOT = app_root()
APP_NAME = "我的桌面导师"
DEFAULT_IMAGE = ROOT / "assets" / "cow.png"
DEFAULT_ICON = ROOT / "assets" / "desktop_mentor.ico"
TODO_BADGE_IMAGE = ROOT / "assets" / "todo_badge.png"
DEFAULT_CLICK_MESSAGE = "我在。把目标和卡点说清楚，我们先找下一步。"
DEFAULT_IDLE_MESSAGE = "进展怎么样？需要我帮你梳理一下下一步吗？"
DEFAULT_DROP_MESSAGE = "文件我收到了。先看目标、约束和你最想解决的问题。"
LEGACY_CLICK_MESSAGES = {"抓紧, 谢谢!"}
LEGACY_IDLE_MESSAGES = {"课题如何了? 抓紧谢谢!"}
LEGACY_DROP_MESSAGES = {"这种垃圾就不要让我看, 我每天很忙的!"}
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
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
APP_ID = "my-desktop-mentor"
DEFAULT_MODEL = "gpt-4o-mini"
CONFIG_POINTER_NAME = "config-dir.txt"
TODO_CHECK_INTERVAL_MS = 1_000
DEFAULT_MESSAGE_SECONDS = 3.2
MIN_MESSAGE_SECONDS = 0.8
MAX_MESSAGE_SECONDS = 60.0
DEFAULT_MEMORY_ENABLED = False
DEFAULT_MEMORY_TURNS = 8
MAX_MEMORY_TURNS = 24
MIN_IDLE_SECONDS = 30
DEFAULT_IDLE_SECONDS = 30
IDLE_CHECK_INTERVAL_MS = 5_000
IDLE_MODE_LIGHT = "light"
IDLE_MODE_FULLSCREEN = "fullscreen"
DEFAULT_IDLE_MODE = IDLE_MODE_LIGHT
IDLE_MODE_OPTIONS = (
    (IDLE_MODE_LIGHT, "轻量气泡"),
    (IDLE_MODE_FULLSCREEN, "满屏提醒"),
)
FULLSCREEN_ALERT_DURATION_MS = 4_200
MAX_DROP_PATHS = 8
MAX_FOLDER_FILES = 36
MAX_PREVIEW_FILES_PER_FOLDER = 6
MAX_FILE_PREVIEW_BYTES = 8192
MAX_DROP_CONTEXT_CHARS = 24_000
TEXT_FILE_SUFFIXES = {
    ".bat",
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".csv",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".log",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".tex",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


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


@dataclass
class AgentConfig:
    api_url: str = ""
    api_key: str = ""
    model: str = DEFAULT_MODEL
    image_path: str = ""
    icon_path: str = ""
    config_dir: str = ""
    click_message: str = DEFAULT_CLICK_MESSAGE
    idle_message: str = DEFAULT_IDLE_MESSAGE
    drop_message: str = DEFAULT_DROP_MESSAGE
    message_seconds: float = DEFAULT_MESSAGE_SECONDS
    idle_seconds: int = DEFAULT_IDLE_SECONDS
    idle_mode: str = DEFAULT_IDLE_MODE
    memory_enabled: bool = DEFAULT_MEMORY_ENABLED
    memory_turns: int = DEFAULT_MEMORY_TURNS
    system_prompt: str = DEFAULT_PERSONALITY_PROMPT


class AgentSignals(QObject):
    reply_ready = Signal(str)


def as_global_pos(widget: QWidget, event_or_point: object) -> QPoint:
    """Return a screen coordinate for mouse or touch input across Qt variants."""
    for name in ("globalPosition", "scenePosition"):
        getter = getattr(event_or_point, name, None)
        if getter is None:
            continue
        try:
            value = getter()
            if isinstance(value, QPointF):
                return value.toPoint()
            if isinstance(value, QPoint):
                return value
        except Exception:
            pass

    pos_getter = getattr(event_or_point, "position", None)
    if pos_getter is not None:
        try:
            value = pos_getter()
            if isinstance(value, QPointF):
                return widget.mapToGlobal(value.toPoint())
            if isinstance(value, QPoint):
                return widget.mapToGlobal(value)
        except Exception:
            pass

    pos_getter = getattr(event_or_point, "pos", None)
    if pos_getter is not None:
        try:
            return widget.mapToGlobal(pos_getter())
        except Exception:
            pass

    return QGuiApplication.primaryScreen().availableGeometry().center()


def as_local_pos(widget: QWidget, event_or_point: object) -> QPoint:
    for name in ("position", "scenePosition"):
        getter = getattr(event_or_point, name, None)
        if getter is None:
            continue
        try:
            value = getter()
            if isinstance(value, QPointF):
                return value.toPoint()
            if isinstance(value, QPoint):
                return value
        except Exception:
            pass

    pos_getter = getattr(event_or_point, "pos", None)
    if pos_getter is not None:
        try:
            return pos_getter()
        except Exception:
            pass

    return widget.mapFromGlobal(as_global_pos(widget, event_or_point))


def default_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "MyDesktopMentor"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MyDesktopMentor"

    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_ID


def config_dir_pointer_path() -> Path:
    return default_config_dir() / CONFIG_POINTER_NAME


def configured_config_dir() -> Path:
    override_dir = os.environ.get("DESKTOP_MENTOR_CONFIG_DIR", "").strip()
    if override_dir:
        return Path(override_dir).expanduser()

    override_file = os.environ.get("DESKTOP_MENTOR_CONFIG", "").strip()
    if override_file:
        return Path(override_file).expanduser().parent

    pointer = config_dir_pointer_path()
    try:
        if pointer.exists():
            raw_path = pointer.read_text(encoding="utf-8").strip()
            if raw_path:
                return Path(raw_path).expanduser()
    except OSError:
        pass

    return default_config_dir()


def config_path() -> Path:
    override = os.environ.get("DESKTOP_MENTOR_CONFIG", "").strip()
    if override:
        return Path(override).expanduser()
    return configured_config_dir() / "config.json"


def save_config_directory(directory: Path) -> Path:
    target = directory.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    pointer = config_dir_pointer_path()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(target), encoding="utf-8")
    return target


def memory_path() -> Path:
    return config_path().parent / "memory.jsonl"


def todos_path() -> Path:
    return config_path().parent / "todos.json"


def load_config(path: Path | None = None) -> AgentConfig:
    target = path or config_path()
    if not target.exists():
        config = AgentConfig()
        config.config_dir = str(target.parent.expanduser())
        return config
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        config = AgentConfig()
        config.config_dir = str(target.parent.expanduser())
        return config

    config = AgentConfig()
    for key in asdict(config):
        if key in data:
            setattr(config, key, data[key])
    config.model = str(config.model or DEFAULT_MODEL)
    config.image_path = str(config.image_path or "").strip()
    config.config_dir = str(target.parent.expanduser())
    config.click_message = str(config.click_message or DEFAULT_CLICK_MESSAGE)
    if config.click_message in LEGACY_CLICK_MESSAGES:
        config.click_message = DEFAULT_CLICK_MESSAGE
    config.idle_message = str(config.idle_message or DEFAULT_IDLE_MESSAGE)
    if config.idle_message in LEGACY_IDLE_MESSAGES:
        config.idle_message = DEFAULT_IDLE_MESSAGE
    config.drop_message = str(config.drop_message or DEFAULT_DROP_MESSAGE)
    if config.drop_message in LEGACY_DROP_MESSAGES:
        config.drop_message = DEFAULT_DROP_MESSAGE
    try:
        config.message_seconds = max(
            MIN_MESSAGE_SECONDS,
            min(MAX_MESSAGE_SECONDS, float(config.message_seconds)),
        )
    except Exception:
        config.message_seconds = DEFAULT_MESSAGE_SECONDS
    try:
        config.idle_seconds = max(MIN_IDLE_SECONDS, int(config.idle_seconds))
    except Exception:
        config.idle_seconds = DEFAULT_IDLE_SECONDS
    config.memory_enabled = bool(config.memory_enabled)
    try:
        config.memory_turns = max(1, min(MAX_MEMORY_TURNS, int(config.memory_turns)))
    except Exception:
        config.memory_turns = DEFAULT_MEMORY_TURNS
    valid_idle_modes = {value for value, _label in IDLE_MODE_OPTIONS}
    config.idle_mode = str(config.idle_mode or DEFAULT_IDLE_MODE)
    if config.idle_mode not in valid_idle_modes:
        config.idle_mode = DEFAULT_IDLE_MODE
    config.system_prompt = str(config.system_prompt or DEFAULT_PERSONALITY_PROMPT)
    if any(marker in config.system_prompt for marker in ("我是长江", "科研老板式", "发 Nature", "这种小事")):
        config.system_prompt = DEFAULT_PERSONALITY_PROMPT
    return config


def save_config(config: AgentConfig, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", path.stem).strip(".-")
    return (stem or "mentor")[:48]


def icon_cache_path_for_image(image_path: Path) -> Path:
    source = image_path.expanduser().resolve()
    digest = file_digest(source)[:16]
    return config_path().parent / "icons" / f"{safe_stem(source)}-{digest}.ico"


def qimage_png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("failed to open PNG buffer")
    if not image.save(buffer, "PNG"):
        raise RuntimeError("failed to encode PNG icon layer")
    buffer.close()
    return bytes(data)


def centered_icon_layer(source: QImage, size: int) -> QImage:
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(canvas)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return canvas


def write_ico(layers: list[tuple[int, bytes]], output_path: Path) -> Path:
    if not layers:
        raise RuntimeError("no icon layers to write")
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    offset = 6 + 16 * len(layers)
    directory = bytearray()
    payload = bytearray()
    for size, data in layers:
        width_byte = 0 if size >= 256 else size
        height_byte = 0 if size >= 256 else size
        directory.extend(struct.pack("<BBBBHHII", width_byte, height_byte, 0, 0, 1, 32, len(data), offset))
        payload.extend(data)
        offset += len(data)

    output_path.write_bytes(struct.pack("<HHH", 0, 1, len(layers)) + bytes(directory) + bytes(payload))
    return output_path


def convert_image_to_ico(image_path: Path, output_path: Path, *, force: bool = True) -> Path:
    source = image_path.expanduser().resolve()
    target = output_path.expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"source image does not exist: {source}")
    if target.exists() and not force:
        try:
            if target.stat().st_mtime >= source.stat().st_mtime and target.stat().st_size > 0:
                return target
        except OSError:
            pass

    image = QImage(str(source))
    if image.isNull():
        raise RuntimeError(f"failed to load source image: {source}")

    layers = [(size, qimage_png_bytes(centered_icon_layer(image, size))) for size in ICON_SIZES]
    return write_ico(layers, target)


def ensure_default_icon(*, force: bool = False) -> Path:
    return convert_image_to_ico(DEFAULT_IMAGE, DEFAULT_ICON, force=force)


def normalize_chat_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def compact_text(text: str, limit: int = 72) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)] + "…"


def local_agent_reply(user_text: str, *, idle: bool = False) -> str:
    if idle:
        return DEFAULT_IDLE_MESSAGE
    text = user_text.lower()
    research_words = (
        "科研",
        "实验",
        "论文",
        "paper",
        "nature",
        "science",
        "计算",
        "模型",
        "催化",
        "量子",
        "药物",
        "数据",
    )
    if any(word in text for word in research_words):
        return "先把问题拆成目标、证据和下一步验证。你把当前材料发我，我们一起把路线理清楚。"
    return "我在。先说目标和卡点，我帮你压缩成下一步行动。"


def load_memory_messages(limit_turns: int) -> list[dict[str, str]]:
    path = memory_path()
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            role = str(item.get("role", ""))
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                rows.append({"role": role, "content": compact_text(content, 1200)})
    except Exception:
        return []
    return rows[-max(2, limit_turns * 2) :]


def append_memory_turn(user_text: str, assistant_text: str) -> None:
    path = memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    records = [
        {"ts": timestamp, "role": "user", "content": compact_text(user_text, 2000)},
        {"ts": timestamp, "role": "assistant", "content": compact_text(assistant_text, 2000)},
    ]
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_todos(path: Path | None = None) -> list[dict[str, object]]:
    target = path or todos_path()
    if not target.exists():
        return []
    try:
        raw_items = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw_items, list):
        return []
    todos: list[dict[str, object]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        try:
            due_ts = int(item.get("due_ts", 0))
        except Exception:
            continue
        if not text or due_ts <= 0:
            continue
        todo_id = str(item.get("id") or f"{due_ts}-{len(todos)}")
        todos.append({"id": todo_id, "text": text, "due_ts": due_ts})
    return sorted(todos, key=lambda row: int(row["due_ts"]))


def save_todos(todos: list[dict[str, object]], path: Path | None = None) -> Path:
    target = path or todos_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    clean_items = load_todos_from_items(todos)
    target.write_text(json.dumps(clean_items, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_todos_from_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    todos: list[dict[str, object]] = []
    for item in items:
        text = str(item.get("text", "")).strip()
        try:
            due_ts = int(item.get("due_ts", 0))
        except Exception:
            continue
        if not text or due_ts <= 0:
            continue
        todos.append({"id": str(item.get("id") or f"{due_ts}-{len(todos)}"), "text": text, "due_ts": due_ts})
    return sorted(todos, key=lambda row: int(row["due_ts"]))


def format_due_time(due_ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(due_ts))


def call_agent(config: AgentConfig, user_text: str) -> str:
    url = normalize_chat_url(config.api_url)
    if not url:
        return local_agent_reply(user_text)

    payload = {
        "model": config.model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": config.system_prompt or DEFAULT_PERSONALITY_PROMPT},
        ],
        "temperature": 0.8,
        "max_tokens": 160,
    }
    if config.memory_enabled:
        payload["messages"].extend(load_memory_messages(config.memory_turns))
    payload["messages"].append({"role": "user", "content": user_text})
    headers = {"Content-Type": "application/json"}
    if config.api_key.strip():
        headers["Authorization"] = f"Bearer {config.api_key.strip()}"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - user-configured endpoint
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return f"接口没接上。我先给本地建议：把目标、材料和卡点列出来。{type(exc).__name__}"

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        content = data.get("response") or data.get("text") or data.get("message") or ""
    return compact_text(str(content or local_agent_reply(user_text)), MAX_BUBBLE_TEXT_CHARS)


def human_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def is_text_like(path: Path, sample: bytes) -> bool:
    if path.suffix.lower() in TEXT_FILE_SUFFIXES:
        return True
    if b"\x00" in sample:
        return False
    if not sample:
        return True
    printable = sum(1 for byte in sample if byte in b"\n\r\t" or 32 <= byte <= 126)
    return printable / max(1, len(sample)) > 0.78


def read_text_preview(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            sample = handle.read(MAX_FILE_PREVIEW_BYTES)
    except OSError as exc:
        return f"[read failed: {type(exc).__name__}]"

    if not is_text_like(path, sample[:2048]):
        return "[binary file omitted]"

    text = sample.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    if len(text) > 4000:
        text = text[:4000] + "\n[preview truncated]"
    return text or "[empty file]"


def describe_file(path: Path, *, base: Path | None = None) -> list[str]:
    try:
        stat = path.stat()
    except OSError as exc:
        return [f"- {path}: [stat failed: {type(exc).__name__}]"]

    label = str(path)
    if base is not None:
        try:
            label = str(path.relative_to(base))
        except ValueError:
            pass

    preview = read_text_preview(path)
    return [
        f"- File: {label}",
        f"  Size: {human_size(stat.st_size)}",
        "  Preview:",
        preview,
    ]


def describe_folder(path: Path) -> list[str]:
    lines = [f"- Folder: {path}"]
    sampled: list[Path] = []
    seen_files = 0
    seen_dirs = 0
    try:
        for child in path.rglob("*"):
            if child.is_dir():
                seen_dirs += 1
                continue
            if not child.is_file():
                continue
            seen_files += 1
            if len(sampled) < MAX_FOLDER_FILES:
                sampled.append(child)
            if seen_files >= MAX_FOLDER_FILES:
                break
    except OSError as exc:
        lines.append(f"  [scan failed: {type(exc).__name__}]")
        return lines

    lines.append(f"  Sampled files: {len(sampled)}")
    if seen_dirs:
        lines.append(f"  Sampled subfolders: {seen_dirs}")
    for file_path in sampled[:MAX_PREVIEW_FILES_PER_FOLDER]:
        lines.extend(describe_file(file_path, base=path))
    if len(sampled) > MAX_PREVIEW_FILES_PER_FOLDER:
        lines.append(f"  [... {len(sampled) - MAX_PREVIEW_FILES_PER_FOLDER} more sampled files omitted]")
    return lines


def collect_drop_context(paths: list[Path]) -> str:
    lines = ["Dropped paths:"]
    for path in paths[:MAX_DROP_PATHS]:
        try:
            if path.is_dir():
                lines.extend(describe_folder(path))
            elif path.is_file():
                lines.extend(describe_file(path))
            else:
                lines.append(f"- {path}: [not a regular file or folder]")
        except OSError as exc:
            lines.append(f"- {path}: [read failed: {type(exc).__name__}]")
    if len(paths) > MAX_DROP_PATHS:
        lines.append(f"[... {len(paths) - MAX_DROP_PATHS} more dropped paths omitted]")

    context = "\n".join(lines)
    if len(context) > MAX_DROP_CONTEXT_CHARS:
        context = context[:MAX_DROP_CONTEXT_CHARS] + "\n[drop context truncated]"
    return context


def windows_system_idle_seconds() -> float | None:
    if sys.platform != "win32":
        return None

    class LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):  # type: ignore[attr-defined]
            return None
        tick = ctypes.windll.kernel32.GetTickCount()  # type: ignore[attr-defined]
    except Exception:
        return None
    return float((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0


def gnome_system_idle_seconds() -> float | None:
    gdbus = shutil.which("gdbus")
    if not gdbus or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return None
    try:
        result = subprocess.run(
            [
                gdbus,
                "call",
                "--session",
                "--dest",
                "org.gnome.Mutter.IdleMonitor",
                "--object-path",
                "/org/gnome/Mutter/IdleMonitor/Core",
                "--method",
                "org.gnome.Mutter.IdleMonitor.GetIdletime",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.6,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"(\d+)", result.stdout)
    if not match:
        return None
    return int(match.group(1)) / 1000.0


def xprintidle_system_idle_seconds() -> float | None:
    xprintidle = shutil.which("xprintidle")
    if not xprintidle or not os.environ.get("DISPLAY"):
        return None
    try:
        result = subprocess.run(
            [xprintidle],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.4,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip()) / 1000.0
    except ValueError:
        return None


def system_idle_seconds() -> float | None:
    if sys.platform == "win32":
        return windows_system_idle_seconds()
    idle = gnome_system_idle_seconds()
    if idle is not None:
        return idle
    return xprintidle_system_idle_seconds()


class SettingsDialog(QDialog):
    def __init__(self, config: AgentConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} 设置")
        self.setStyleSheet(APP_STYLESHEET)
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        self.resize(min(740, max(560, available.width() - 120)), min(760, max(460, available.height() - 120)))
        self.setMinimumSize(520, 420)

        self.url_edit = QLineEdit(config.api_url)
        self.url_edit.setPlaceholderText("OpenAI-compatible base URL, e.g. http://127.0.0.1:8000")

        self.key_edit = QLineEdit(config.api_key)
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("API key")

        self.model_edit = QLineEdit(config.model or DEFAULT_MODEL)

        self.config_dir_edit = QLineEdit(config.config_dir or str(config_path().parent))
        self.config_dir_edit.setPlaceholderText("runtime config directory")
        config_dir_button = QPushButton("选择")
        config_dir_button.clicked.connect(self.browse_config_dir)
        config_dir_row = QHBoxLayout()
        config_dir_row.addWidget(self.config_dir_edit, 1)
        config_dir_row.addWidget(config_dir_button)

        self.image_edit = QLineEdit(config.image_path or str(DEFAULT_IMAGE))
        self.image_edit.setPlaceholderText("PNG/JPG image path; PNG will be converted to ICO")
        image_button = QPushButton("选择")
        image_button.clicked.connect(self.browse_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_edit, 1)
        image_row.addWidget(image_button)

        self.click_message_edit = QLineEdit(config.click_message or DEFAULT_CLICK_MESSAGE)
        self.click_message_edit.setPlaceholderText("点击/触摸桌宠时显示的话")

        self.idle_message_edit = QLineEdit(config.idle_message or DEFAULT_IDLE_MESSAGE)
        self.idle_message_edit.setPlaceholderText("空闲提醒时显示的话")

        self.drop_message_edit = QLineEdit(config.drop_message or DEFAULT_DROP_MESSAGE)
        self.drop_message_edit.setPlaceholderText("拖放文件/文件夹时显示的话")

        self.message_seconds_spin = QDoubleSpinBox()
        self.message_seconds_spin.setRange(MIN_MESSAGE_SECONDS, MAX_MESSAGE_SECONDS)
        self.message_seconds_spin.setSingleStep(0.5)
        self.message_seconds_spin.setDecimals(1)
        self.message_seconds_spin.setValue(max(MIN_MESSAGE_SECONDS, min(MAX_MESSAGE_SECONDS, float(config.message_seconds or DEFAULT_MESSAGE_SECONDS))))
        self.message_seconds_spin.setSuffix(" s")

        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(MIN_IDLE_SECONDS, 86400)
        self.idle_spin.setSingleStep(10)
        self.idle_spin.setValue(max(MIN_IDLE_SECONDS, int(config.idle_seconds or DEFAULT_IDLE_SECONDS)))
        self.idle_spin.setSuffix(" s")

        self.idle_mode_combo = QComboBox()
        for mode, label in IDLE_MODE_OPTIONS:
            self.idle_mode_combo.addItem(label, mode)
        idle_mode_index = self.idle_mode_combo.findData(config.idle_mode or DEFAULT_IDLE_MODE)
        self.idle_mode_combo.setCurrentIndex(max(0, idle_mode_index))

        self.memory_check = QCheckBox("保留最近对话作为上下文")
        self.memory_check.setChecked(bool(config.memory_enabled))

        self.memory_turns_spin = QSpinBox()
        self.memory_turns_spin.setRange(1, MAX_MEMORY_TURNS)
        self.memory_turns_spin.setValue(max(1, min(MAX_MEMORY_TURNS, int(config.memory_turns or DEFAULT_MEMORY_TURNS))))
        self.memory_turns_spin.setSuffix(" turns")

        self.prompt_edit = QTextEdit(config.system_prompt or DEFAULT_PERSONALITY_PROMPT)
        self.prompt_edit.setMinimumHeight(220)

        title = QLabel("Agent 设置")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        subtitle = QLabel("配置 agent 接口、桌宠形象、交互话术和空闲提醒。")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.addRow("Agent URL", self.url_edit)
        form.addRow("API Key", self.key_edit)
        form.addRow("Model", self.model_edit)
        form.addRow("Config directory", config_dir_row)
        form.addRow("Pet image", image_row)
        form.addRow("Click message", self.click_message_edit)
        form.addRow("Idle message", self.idle_message_edit)
        form.addRow("Drop message", self.drop_message_edit)
        form.addRow("Message duration", self.message_seconds_spin)
        form.addRow("Idle reminder", self.idle_spin)
        form.addRow("Idle mode", self.idle_mode_combo)
        form.addRow("Memory", self.memory_check)
        form.addRow("Memory depth", self.memory_turns_spin)
        form.addRow("Style prompt", self.prompt_edit)

        reset_prompt = QPushButton("恢复默认人格")
        reset_prompt.clicked.connect(lambda: self.prompt_edit.setPlainText(DEFAULT_PERSONALITY_PROMPT))

        hint = QLabel("配置保存在当前系统用户配置目录，不写入项目仓库。PNG 形象会自动生成 ICO。URL 按 OpenAI-compatible /v1/chat/completions 调用。")
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        hint.setStyleSheet("#hint { color: #94a3b8; background: #0b1220; border: 1px solid #1f2a3a; border-radius: 8px; padding: 10px; }")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addWidget(reset_prompt)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 20, 22, 20)
        content_layout.setSpacing(14)
        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addWidget(hint)
        content_layout.addLayout(form)
        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(scroll, 1)
        bottom_container = QWidget()
        bottom_container.setObjectName("settingsFooter")
        bottom_container.setStyleSheet("#settingsFooter { border-top: 1px solid #263244; background: #111827; }")
        bottom_container.setLayout(bottom)
        bottom.setContentsMargins(22, 12, 22, 12)
        layout.addWidget(bottom_container, 0)

    def browse_image(self) -> None:
        current = self.image_edit.text().strip()
        start_dir = str(Path(current).expanduser().parent) if current else str(Path.home())
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择桌宠形象",
            start_dir,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if path:
            self.image_edit.setText(path)

    def browse_config_dir(self) -> None:
        current = self.config_dir_edit.text().strip() or str(config_path().parent)
        path = QFileDialog.getExistingDirectory(self, "选择配置目录", str(Path(current).expanduser()))
        if path:
            self.config_dir_edit.setText(path)

    def image_path_value(self) -> str:
        raw_path = self.image_edit.text().strip()
        if not raw_path:
            return ""
        try:
            if Path(raw_path).expanduser().resolve() == DEFAULT_IMAGE.expanduser().resolve():
                return ""
        except OSError:
            pass
        return raw_path

    def to_config(self) -> AgentConfig:
        return AgentConfig(
            api_url=self.url_edit.text().strip(),
            api_key=self.key_edit.text().strip(),
            model=self.model_edit.text().strip() or DEFAULT_MODEL,
            config_dir=self.config_dir_edit.text().strip() or str(config_path().parent),
            image_path=self.image_path_value(),
            click_message=self.click_message_edit.text().strip() or DEFAULT_CLICK_MESSAGE,
            idle_message=self.idle_message_edit.text().strip() or DEFAULT_IDLE_MESSAGE,
            drop_message=self.drop_message_edit.text().strip() or DEFAULT_DROP_MESSAGE,
            message_seconds=float(self.message_seconds_spin.value()),
            idle_seconds=int(self.idle_spin.value()),
            idle_mode=str(self.idle_mode_combo.currentData() or DEFAULT_IDLE_MODE),
            memory_enabled=self.memory_check.isChecked(),
            memory_turns=int(self.memory_turns_spin.value()),
            system_prompt=self.prompt_edit.toPlainText().strip() or DEFAULT_PERSONALITY_PROMPT,
        )


class ChatDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"问{APP_NAME}")
        self.setStyleSheet(APP_STYLESHEET)
        self.resize(420, 260)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("你要问什么")
        self.text_edit.setMinimumHeight(150)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("发送")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.text_edit)
        layout.addWidget(buttons)

    def text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.text_edit.setFocus(Qt.FocusReason.OtherFocusReason)


class TodoDialog(QDialog):
    def __init__(self, todos: list[dict[str, object]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("待办提醒")
        self.setStyleSheet(APP_STYLESHEET)
        self.resize(560, 460)
        self.todos = load_todos_from_items(todos)

        header = QHBoxLayout()
        badge = QLabel()
        pixmap = QPixmap(str(TODO_BADGE_IMAGE))
        if not pixmap.isNull():
            badge.setPixmap(pixmap.scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        title = QLabel("待办")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        header.addWidget(badge)
        header.addWidget(title)
        header.addStretch(1)

        self.todo_edit = QLineEdit()
        self.todo_edit.setPlaceholderText("要提醒的事情")

        self.due_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(30 * 60))
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDisplayFormat("yyyy-MM-dd HH:mm")

        add_button = QPushButton("添加")
        add_button.clicked.connect(self.add_todo)

        editor = QHBoxLayout()
        editor.addWidget(self.todo_edit, 1)
        editor.addWidget(self.due_edit)
        editor.addWidget(add_button)

        self.todo_list = QListWidget()
        self.todo_list.setMinimumHeight(220)

        remove_button = QPushButton("删除选中")
        remove_button.clicked.connect(self.remove_selected)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addWidget(remove_button)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addLayout(editor)
        layout.addWidget(self.todo_list, 1)
        layout.addLayout(bottom)
        self.refresh_list()

    def refresh_list(self) -> None:
        self.todo_list.clear()
        now_ts = int(time.time())
        for todo in self.todos:
            due_ts = int(todo["due_ts"])
            prefix = "到期" if due_ts <= now_ts else format_due_time(due_ts)
            item = QListWidgetItem(f"{prefix}  {todo['text']}")
            item.setData(Qt.ItemDataRole.UserRole, str(todo["id"]))
            self.todo_list.addItem(item)

    def add_todo(self) -> None:
        text = self.todo_edit.text().strip()
        if not text:
            return
        due_ts = int(self.due_edit.dateTime().toSecsSinceEpoch())
        todo = {"id": f"{int(time.time() * 1000)}-{len(self.todos)}", "text": text, "due_ts": due_ts}
        self.todos.append(todo)
        self.todos = load_todos_from_items(self.todos)
        self.todo_edit.clear()
        self.due_edit.setDateTime(QDateTime.currentDateTime().addSecs(30 * 60))
        self.refresh_list()

    def remove_selected(self) -> None:
        ids = {str(item.data(Qt.ItemDataRole.UserRole)) for item in self.todo_list.selectedItems()}
        if not ids:
            return
        self.todos = [todo for todo in self.todos if str(todo["id"]) not in ids]
        self.refresh_list()


class FullScreenIdleAlert(QWidget):
    def __init__(self, message: str, duration_ms: int = FULLSCREEN_ALERT_DURATION_MS) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.message = compact_text(message, 140)
        self.duration_ms = duration_ms
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    @staticmethod
    def virtual_screen_geometry() -> QRect:
        screens = QGuiApplication.screens()
        if not screens:
            screen = QGuiApplication.primaryScreen()
            return screen.geometry() if screen else QRect(0, 0, 1280, 720)
        geometry = screens[0].geometry()
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        return geometry

    def show_alert(self) -> None:
        self.setGeometry(self.virtual_screen_geometry())
        self.show()
        self.raise_()
        self.close_timer.start(self.duration_ms)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(8, 10, 16, 215))

        card_width = min(max(520, int(self.width() * 0.62)), 980)
        card_height = min(max(260, int(self.height() * 0.34)), 430)
        card = QRectF(
            (self.width() - card_width) / 2,
            (self.height() - card_height) / 2,
            card_width,
            card_height,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 110))
        painter.drawRoundedRect(card.translated(0, 8), 24, 24)
        painter.setBrush(QColor(25, 30, 38, 244))
        painter.drawRoundedRect(card, 24, 24)

        font = QFont()
        font.setPointSize(max(34, min(82, int(min(self.width(), self.height()) / 14))))
        font.setWeight(QFont.Weight.Black)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            card.adjusted(38, 26, -38, -26),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.message,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self.close()
        event.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        self.close()
        event.accept()

    def event(self, event) -> bool:  # type: ignore[override]
        if event.type() in {QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd}:
            self.close()
            event.accept()
            return True
        return super().event(event)


class DesktopMentorPet(QWidget):
    def __init__(self, image_path: Path, message: str, size: int) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.default_message = message
        self.current_message = message
        self.pet_size = max(96, min(420, size))
        self.bubble_width = BUBBLE_MIN_WIDTH
        self.bubble_body_height = BUBBLE_BODY_MIN_HEIGHT
        self.bubble_height = BUBBLE_MIN_HEIGHT
        self.config_path = config_path()
        self.config = load_config(self.config_path)
        if not self.config.click_message:
            self.config.click_message = message or DEFAULT_CLICK_MESSAGE
        self.image_path = self.effective_image_path(image_path)
        self.pixmap = QPixmap(str(self.image_path))
        if self.pixmap.isNull():
            fallback_pixmap = QPixmap(str(image_path))
            if fallback_pixmap.isNull():
                raise RuntimeError(f"failed to load image: {self.image_path}")
            self.image_path = image_path
            self.pixmap = fallback_pixmap
            self.config.image_path = str(image_path)
        self.fullscreen_alert: FullScreenIdleAlert | None = None
        self.icon_error = self.refresh_window_icon()

        self.dragging = False
        self.drag_offset = QPoint()
        self.drag_start = QPoint()
        self.last_drag_pos = QPoint()
        self.touch_dragging = False
        self.touch_start_pos = QPoint()
        self.touch_long_press_menu_opened = False
        self.last_drop_context = ""
        self.last_drop_paths: list[str] = []
        self.chat_button_pressed = False
        self.settings_button_pressed = False
        self.quit_button_pressed = False
        self.drop_hover = False
        self.drop_effect_until = 0.0
        self.drag_effect_until = 0.0
        self.pulse_until = 0.0
        self.message_until = 0.0
        self.last_interaction = time.monotonic()
        self.idle_suppressed_until = 0.0
        self.hovering = False
        self.agent_signals = AgentSignals()
        self.agent_signals.reply_ready.connect(self.show_agent_reply)

        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(16)
        self.pulse_timer.timeout.connect(self.animation_tick)
        self.drag_follow_timer = QTimer(self)
        self.drag_follow_timer.setInterval(16)
        self.drag_follow_timer.timeout.connect(self.follow_drag_pointer)
        self.touch_menu_timer = QTimer(self)
        self.touch_menu_timer.setSingleShot(True)
        self.touch_menu_timer.timeout.connect(self.open_touch_menu)
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(IDLE_CHECK_INTERVAL_MS)
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start()
        self.todo_timer = QTimer(self)
        self.todo_timer.setInterval(TODO_CHECK_INTERVAL_MS)
        self.todo_timer.timeout.connect(self.check_todos)
        self.todo_timer.start()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(*self.window_dimensions())
        self.move_to_lower_right()

    def effective_image_path(self, fallback: Path = DEFAULT_IMAGE) -> Path:
        raw_path = str(self.config.image_path or "").strip()
        if not raw_path:
            return fallback.expanduser().resolve()
        return Path(raw_path).expanduser().resolve()

    def apply_image_from_config(self, fallback: Path | None = None) -> bool:
        image_path = self.effective_image_path(fallback or DEFAULT_IMAGE)
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return False
        self.image_path = image_path
        self.pixmap = pixmap
        self.update()
        return True

    def refresh_window_icon(self) -> str:
        try:
            if self.image_path.suffix.lower() == ".png":
                default_source = self.image_path == DEFAULT_IMAGE.expanduser().resolve()
                icon_path = ensure_default_icon() if default_source else convert_image_to_ico(
                    self.image_path,
                    icon_cache_path_for_image(self.image_path),
                    force=False,
                )
                self.config.icon_path = str(icon_path)
                self.setWindowIcon(QIcon(str(icon_path)))
                return ""

            raw_icon = str(self.config.icon_path or "").strip()
            if raw_icon and Path(raw_icon).expanduser().exists():
                self.setWindowIcon(QIcon(str(Path(raw_icon).expanduser())))
                return ""
            self.config.icon_path = ""
            return ""
        except Exception as exc:
            self.config.icon_path = ""
            return f"{type(exc).__name__}: {exc}"

    def window_dimensions(self) -> tuple[int, int]:
        rail_width = self.action_rail_width()
        width = max(
            self.pet_size + WINDOW_PAD * 2 + rail_width + DROP_HOTZONE_PAD * 2,
            int(self.bubble_width + 12),
            BUBBLE_MIN_WIDTH,
        )
        height = self.pet_size + WINDOW_PAD * 2 + int(self.bubble_height) + DROP_HOTZONE_PAD
        return width, height

    def move_to_lower_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 48, area.bottom() - self.height() - 64)

    def show_message(self) -> None:
        self.show_bubble(self.config.click_message or self.default_message or DEFAULT_CLICK_MESSAGE, duration=self.message_duration())

    def message_duration(self) -> float:
        try:
            return max(MIN_MESSAGE_SECONDS, min(MAX_MESSAGE_SECONDS, float(self.config.message_seconds)))
        except Exception:
            return DEFAULT_MESSAGE_SECONDS

    def show_bubble(self, text: str, duration: float = 1.65) -> None:
        now = time.monotonic()
        self.current_message = compact_text(text, MAX_BUBBLE_TEXT_CHARS)
        self.apply_bubble_layout(self.current_message)
        self.pulse_until = now + 0.38
        self.message_until = now + duration
        if not self.pulse_timer.isActive():
            self.pulse_timer.start()
        self.update()

    def start_visual_effect(self, duration: float) -> None:
        if not self.pulse_timer.isActive():
            self.pulse_timer.start()
        self.update()

    def show_agent_reply(self, text: str) -> None:
        self.show_bubble(text, duration=self.message_duration())

    def mark_interaction(self) -> None:
        self.last_interaction = time.monotonic()

    def check_idle(self) -> None:
        if time.monotonic() < self.idle_suppressed_until:
            return
        if any(int(todo["due_ts"]) <= int(time.time()) for todo in load_todos()):
            return
        idle_seconds = max(MIN_IDLE_SECONDS, int(self.config.idle_seconds or DEFAULT_IDLE_SECONDS))
        idle_for = system_idle_seconds()
        if idle_for is None:
            idle_for = time.monotonic() - self.last_interaction
        if idle_for < idle_seconds:
            return
        self.show_idle_reminder()

    def show_idle_reminder(self) -> None:
        message = self.config.idle_message or DEFAULT_IDLE_MESSAGE
        if self.config.idle_mode == IDLE_MODE_FULLSCREEN:
            self.show_fullscreen_idle(message)
            return
        self.show_bubble(message, duration=self.message_duration())

    def clear_fullscreen_alert(self, alert: FullScreenIdleAlert) -> None:
        if self.fullscreen_alert is alert:
            self.fullscreen_alert = None

    def show_fullscreen_idle(self, text: str) -> None:
        if self.fullscreen_alert is not None:
            self.fullscreen_alert.close()
        alert = FullScreenIdleAlert(text, int(self.message_duration() * 1000))
        self.fullscreen_alert = alert
        alert.destroyed.connect(lambda _obj=None, target=alert: self.clear_fullscreen_alert(target))
        alert.show_alert()

    def animation_tick(self) -> None:
        now = time.monotonic()
        self.update()
        if (
            now >= self.pulse_until
            and now >= self.message_until
            and now >= self.drag_effect_until
            and now >= self.drop_effect_until
            and not self.drop_hover
            and not self.dragging
        ):
            self.pulse_timer.stop()
            self.reset_bubble_layout()

    @staticmethod
    def bubble_font() -> QFont:
        font = QFont()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def calculate_bubble_layout(self, text: str) -> tuple[int, int, int]:
        font_metrics = QFontMetrics(self.bubble_font())
        lines = str(text or "").splitlines() or [""]
        single_line_width = max(font_metrics.horizontalAdvance(line) for line in lines)
        length_width = BUBBLE_MIN_WIDTH + max(0, min(BUBBLE_MAX_WIDTH - BUBBLE_MIN_WIDTH, (len(text) - 34) * 4))
        body_width = int(
            max(
                BUBBLE_MIN_WIDTH,
                min(BUBBLE_MAX_WIDTH, max(length_width, single_line_width + BUBBLE_TEXT_PAD_X * 2)),
            )
        )
        text_width = max(80, body_width - BUBBLE_TEXT_PAD_X * 2)
        text_rect = font_metrics.boundingRect(
            0,
            0,
            text_width,
            4000,
            int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
            text or " ",
        )
        body_height = int(
            max(
                BUBBLE_BODY_MIN_HEIGHT,
                min(BUBBLE_BODY_MAX_HEIGHT, text_rect.height() + BUBBLE_TEXT_PAD_Y * 2),
            )
        )
        bubble_height = max(BUBBLE_MIN_HEIGHT, body_height + BUBBLE_TOP + BUBBLE_TAIL_HEIGHT + BUBBLE_BOTTOM_PAD)
        return body_width, body_height, bubble_height

    def sticker_center_global(self) -> QPoint:
        return self.frameGeometry().topLeft() + self.sticker_rect().center().toPoint()

    def resize_preserving_sticker(self) -> None:
        old_center = self.sticker_center_global()
        self.resize(*self.window_dimensions())
        self.move(old_center - self.sticker_rect().center().toPoint())

    def apply_bubble_layout(self, text: str) -> None:
        width, body_height, height = self.calculate_bubble_layout(text)
        if (
            width == self.bubble_width
            and body_height == self.bubble_body_height
            and height == self.bubble_height
        ):
            return
        self.bubble_width = width
        self.bubble_body_height = body_height
        self.bubble_height = height
        self.resize_preserving_sticker()

    def reset_bubble_layout(self) -> None:
        if (
            self.bubble_width == BUBBLE_MIN_WIDTH
            and self.bubble_body_height == BUBBLE_BODY_MIN_HEIGHT
            and self.bubble_height == BUBBLE_MIN_HEIGHT
        ):
            return
        self.bubble_width = BUBBLE_MIN_WIDTH
        self.bubble_body_height = BUBBLE_BODY_MIN_HEIGHT
        self.bubble_height = BUBBLE_MIN_HEIGHT
        self.resize_preserving_sticker()

    def scale(self) -> float:
        remaining = self.pulse_until - time.monotonic()
        if remaining <= 0:
            return 1.0
        phase = (0.38 - remaining) / 0.38
        return 1.0 + 0.055 * math.sin(math.pi * phase)

    def begin_drag(self, global_pos: QPoint, *, touch: bool = False) -> None:
        self.mark_interaction()
        self.dragging = True
        self.touch_dragging = touch
        self.drag_start = global_pos
        self.last_drag_pos = global_pos
        self.drag_offset = global_pos - self.frameGeometry().topLeft()
        self.raise_()
        self.drag_effect_until = time.monotonic() + DRAG_RELEASE_EFFECT_DURATION
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.start_visual_effect(DRAG_RELEASE_EFFECT_DURATION)
        self.show_message()
        if touch:
            self.touch_start_pos = global_pos
            self.touch_long_press_menu_opened = False
            self.touch_menu_timer.start(620)
        if touch and not self.drag_follow_timer.isActive():
            self.drag_follow_timer.start()

    def move_from_pointer(self, global_pos: QPoint) -> None:
        if self.touch_dragging and self.touch_menu_timer.isActive():
            delta = global_pos - self.touch_start_pos
            if abs(delta.x()) + abs(delta.y()) > 10:
                self.touch_menu_timer.stop()
        self.last_drag_pos = global_pos
        self.move(global_pos - self.drag_offset)

    def follow_drag_pointer(self) -> None:
        if not self.dragging or not self.touch_dragging:
            self.drag_follow_timer.stop()
            return
        pointer = self.last_drag_pos
        if not pointer.isNull():
            self.move(pointer - self.drag_offset)

    def end_drag(self) -> None:
        self.dragging = False
        self.touch_dragging = False
        self.drag_follow_timer.stop()
        self.touch_menu_timer.stop()
        self.drag_effect_until = time.monotonic() + DRAG_RELEASE_EFFECT_DURATION
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.hovering else Qt.CursorShape.ArrowCursor)
        self.start_visual_effect(DRAG_RELEASE_EFFECT_DURATION)

    def action_button_size(self) -> int:
        return max(ACTION_BUTTON_MIN_SIZE, min(ACTION_BUTTON_MAX_SIZE, int(self.pet_size * 0.24)))

    def action_rail_width(self) -> int:
        return self.action_button_size() + ACTION_BUTTON_STICKER_GAP + ACTION_BUTTON_OUTER_PAD

    def action_button_rects(self) -> tuple[QRectF, QRectF, QRectF]:
        sticker = self.sticker_rect()
        size = self.action_button_size()
        total_height = size * 3 + ACTION_BUTTON_GAP * 2
        x = sticker.right() + ACTION_BUTTON_STICKER_GAP
        y = sticker.bottom() - total_height - ACTION_BUTTON_OUTER_PAD
        y = max(sticker.top() + ACTION_BUTTON_OUTER_PAD, min(y, sticker.bottom() - total_height - ACTION_BUTTON_OUTER_PAD))
        chat = QRectF(x, y, size, size)
        settings = QRectF(x, y + size + ACTION_BUTTON_GAP, size, size)
        quit_button = QRectF(x, y + (size + ACTION_BUTTON_GAP) * 2, size, size)
        return chat, settings, quit_button

    def settings_button_rect(self) -> QRectF:
        return self.action_button_rects()[1]

    def chat_button_rect(self) -> QRectF:
        return self.action_button_rects()[0]

    def quit_button_rect(self) -> QRectF:
        return self.action_button_rects()[2]

    def point_in_chat_button(self, point: QPoint) -> bool:
        return self.chat_button_rect().contains(QPointF(point))

    def point_in_settings_button(self, point: QPoint) -> bool:
        return self.settings_button_rect().contains(QPointF(point))

    def point_in_quit_button(self, point: QPoint) -> bool:
        return self.quit_button_rect().contains(QPointF(point))

    def point_in_action_button(self, point: QPoint) -> bool:
        return self.point_in_chat_button(point) or self.point_in_settings_button(point) or self.point_in_quit_button(point)

    def activate_chat_button(self) -> None:
        self.chat_button_pressed = False
        self.update()
        self.open_chat()

    def activate_settings_button(self) -> None:
        self.settings_button_pressed = False
        self.update()
        self.open_settings()

    def activate_quit_button(self) -> None:
        self.quit_button_pressed = False
        self.update()
        QApplication.quit()

    def open_touch_menu(self) -> None:
        if not self.touch_dragging:
            return
        self.touch_long_press_menu_opened = True
        self.end_drag()
        self.open_menu(self.last_drag_pos if not self.last_drag_pos.isNull() else self.mapToGlobal(self.rect().center()))

    @staticmethod
    def local_drop_paths(event) -> list[Path]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        paths: list[Path] = []
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            local_path = url.toLocalFile()
            if local_path:
                paths.append(Path(local_path))
        return paths

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self.local_drop_paths(event):
            self.raise_()
            self.drop_hover = True
            self.drop_effect_until = time.monotonic() + DROP_EFFECT_DURATION
            self.setCursor(Qt.CursorShape.DragCopyCursor)
            self.start_visual_effect(DROP_EFFECT_DURATION)
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.local_drop_paths(event):
            self.drop_hover = True
            self.drop_effect_until = time.monotonic() + DROP_EFFECT_DURATION
            self.start_visual_effect(DROP_EFFECT_DURATION)
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.drop_hover = False
        if not self.dragging:
            self.unsetCursor()
        self.drop_effect_until = time.monotonic() + 0.18
        self.start_visual_effect(0.18)
        event.accept()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = self.local_drop_paths(event)
        if not paths:
            super().dropEvent(event)
            return
        self.mark_interaction()
        self.drop_hover = False
        self.drop_effect_until = time.monotonic() + DROP_EFFECT_DURATION
        self.unsetCursor()
        self.last_drop_paths = [str(path) for path in paths]
        self.last_drop_context = collect_drop_context(paths)
        self.show_bubble(self.config.drop_message or DEFAULT_DROP_MESSAGE, duration=self.message_duration())
        event.acceptProposedAction()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self.mark_interaction()
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = as_local_pos(self, event)
            if self.point_in_chat_button(local_pos):
                self.chat_button_pressed = True
                self.update()
                event.accept()
                return
            if self.point_in_settings_button(local_pos):
                self.settings_button_pressed = True
                self.update()
                event.accept()
                return
            if self.point_in_quit_button(local_pos):
                self.quit_button_pressed = True
                self.update()
                event.accept()
                return
            self.begin_drag(as_global_pos(self, event))
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.open_menu(as_global_pos(self, event))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        local_pos = as_local_pos(self, event)
        if self.settings_button_pressed:
            self.settings_button_pressed = self.point_in_settings_button(local_pos)
            self.update()
            event.accept()
            return
        if self.quit_button_pressed:
            self.quit_button_pressed = self.point_in_quit_button(local_pos)
            self.update()
            event.accept()
            return
        if self.chat_button_pressed:
            self.chat_button_pressed = self.point_in_chat_button(local_pos)
            self.update()
            event.accept()
            return
        if self.dragging and not self.touch_dragging:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                self.end_drag()
                event.accept()
                return
            self.move_from_pointer(as_global_pos(self, event))
            event.accept()
            return
        if self.dragging and self.touch_dragging:
            event.accept()
            return
        if self.point_in_action_button(local_pos):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif self.sticker_rect().contains(QPointF(local_pos)):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.settings_button_pressed:
            if self.point_in_settings_button(as_local_pos(self, event)):
                self.activate_settings_button()
            else:
                self.settings_button_pressed = False
                self.update()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.quit_button_pressed:
            if self.point_in_quit_button(as_local_pos(self, event)):
                self.activate_quit_button()
            else:
                self.quit_button_pressed = False
                self.update()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.chat_button_pressed:
            if self.point_in_chat_button(as_local_pos(self, event)):
                self.activate_chat_button()
            else:
                self.chat_button_pressed = False
                self.update()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.dragging and not self.touch_dragging:
            self.end_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, _event) -> None:  # type: ignore[override]
        self.hovering = True
        self.update()

    def leaveEvent(self, _event) -> None:  # type: ignore[override]
        self.hovering = False
        if not self.chat_button_pressed and not self.settings_button_pressed and not self.quit_button_pressed:
            self.unsetCursor()
        self.update()

    def event(self, event) -> bool:  # type: ignore[override]
        event_type = event.type()
        if event_type in {
            QEvent.Type.TouchBegin,
            QEvent.Type.TouchUpdate,
            QEvent.Type.TouchEnd,
            QEvent.Type.TouchCancel,
        }:
            points = event.points()
            if not points:
                return True
            point = points[0]
            local_pos = as_local_pos(self, point)
            global_pos = as_global_pos(self, point)

            if event_type == QEvent.Type.TouchBegin:
                if self.point_in_chat_button(local_pos):
                    self.chat_button_pressed = True
                    self.update()
                    event.accept()
                    return True
                if self.point_in_settings_button(local_pos):
                    self.settings_button_pressed = True
                    self.update()
                    event.accept()
                    return True
                if self.point_in_quit_button(local_pos):
                    self.quit_button_pressed = True
                    self.update()
                    event.accept()
                    return True
                self.begin_drag(global_pos, touch=True)
            elif event_type == QEvent.Type.TouchUpdate and self.settings_button_pressed:
                self.settings_button_pressed = self.point_in_settings_button(local_pos)
                self.update()
            elif event_type == QEvent.Type.TouchUpdate and self.chat_button_pressed:
                self.chat_button_pressed = self.point_in_chat_button(local_pos)
                self.update()
            elif event_type == QEvent.Type.TouchUpdate and self.quit_button_pressed:
                self.quit_button_pressed = self.point_in_quit_button(local_pos)
                self.update()
            elif event_type == QEvent.Type.TouchEnd and self.settings_button_pressed:
                if self.point_in_settings_button(local_pos):
                    self.activate_settings_button()
                else:
                    self.settings_button_pressed = False
                    self.update()
            elif event_type == QEvent.Type.TouchEnd and self.chat_button_pressed:
                if self.point_in_chat_button(local_pos):
                    self.activate_chat_button()
                else:
                    self.chat_button_pressed = False
                    self.update()
            elif event_type == QEvent.Type.TouchEnd and self.quit_button_pressed:
                if self.point_in_quit_button(local_pos):
                    self.activate_quit_button()
                else:
                    self.quit_button_pressed = False
                    self.update()
            elif event_type == QEvent.Type.TouchUpdate and self.touch_dragging:
                self.move_from_pointer(global_pos)
            else:
                self.settings_button_pressed = False
                self.chat_button_pressed = False
                self.quit_button_pressed = False
                self.end_drag()
            event.accept()
            return True
        return super().event(event)

    def open_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(APP_STYLESHEET)
        chat = QAction("对话", self)
        todo_action = QAction("待办", self)
        settings = QAction("Agent 设置", self)
        quit_action = QAction("退出", self)
        bigger = QAction("放大", self)
        smaller = QAction("缩小", self)
        reset = QAction("回到右下角", self)
        chat.triggered.connect(self.open_chat)
        todo_action.triggered.connect(self.open_todos)
        settings.triggered.connect(self.open_settings)
        quit_action.triggered.connect(QApplication.quit)
        bigger.triggered.connect(lambda: self.set_pet_size(self.pet_size + 28))
        smaller.triggered.connect(lambda: self.set_pet_size(self.pet_size - 28))
        reset.triggered.connect(self.move_to_lower_right)
        menu.addAction(chat)
        menu.addAction(todo_action)
        menu.addAction(settings)
        menu.addAction(quit_action)
        menu.addSeparator()
        menu.addAction(bigger)
        menu.addAction(smaller)
        menu.addSeparator()
        menu.addAction(reset)
        menu.exec(pos)

    def open_settings(self) -> None:
        self.mark_interaction()
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            old_config = self.config
            old_config_path = self.config_path
            old_image_path = self.image_path
            old_pixmap = self.pixmap
            new_config = dialog.to_config()
            requested_config_dir = Path(new_config.config_dir or str(self.config_path.parent)).expanduser()
            try:
                resolved_config_dir = requested_config_dir.resolve()
                resolved_config_dir.mkdir(parents=True, exist_ok=True)
                new_config.config_dir = str(resolved_config_dir)
                self.config_path = resolved_config_dir / "config.json"
            except OSError as exc:
                self.show_bubble(f"配置目录不可用：{type(exc).__name__}", duration=self.message_duration())
                return
            self.config = new_config
            if not self.apply_image_from_config(old_image_path):
                self.config = old_config
                self.config_path = old_config_path
                self.image_path = old_image_path
                self.pixmap = old_pixmap
                self.show_bubble("形象文件加载失败，设置未保存。", duration=self.message_duration())
                return
            icon_error = self.refresh_window_icon()
            saved_dir = save_config_directory(resolved_config_dir)
            self.config.config_dir = str(saved_dir)
            self.config_path = saved_dir / "config.json"
            path = save_config(self.config, self.config_path)
            if self.config.idle_mode != IDLE_MODE_FULLSCREEN and self.fullscreen_alert is not None:
                self.fullscreen_alert.close()
            if icon_error:
                self.show_bubble(f"设置已保存，但 ICO 生成失败：{icon_error}", duration=self.message_duration())
            else:
                self.show_bubble(f"设置已保存：{path}", duration=self.message_duration())

    def open_todos(self) -> None:
        self.mark_interaction()
        dialog = TodoDialog(load_todos(), self)
        self.position_dialog_near_pet(dialog)
        dialog.exec()
        path = save_todos(dialog.todos)
        self.show_bubble(f"待办已保存：{path}", duration=self.message_duration())

    def check_todos(self) -> None:
        now_ts = int(time.time())
        todos = load_todos()
        due = [todo for todo in todos if int(todo["due_ts"]) <= now_ts]
        if not due:
            return
        remaining = [todo for todo in todos if int(todo["due_ts"]) > now_ts]
        save_todos(remaining)
        if self.fullscreen_alert is not None:
            self.fullscreen_alert.close()
        self.idle_suppressed_until = time.monotonic() + max(8.0, self.message_duration() + 3.0)
        shown = "；".join(str(todo["text"]) for todo in due[:3])
        if len(due) > 3:
            shown += f"；还有 {len(due) - 3} 项"
        self.show_bubble(f"待办提醒：{shown}", duration=self.message_duration())

    def open_chat(self) -> None:
        self.mark_interaction()
        dialog = ChatDialog(self)
        self.position_dialog_near_pet(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        prompt = dialog.text()
        if not prompt:
            return
        self.show_bubble("导师处理中。", duration=min(1.8, self.message_duration()))
        thread = threading.Thread(target=self.fetch_agent_reply, args=(prompt,), daemon=True)
        thread.start()

    def position_dialog_near_pet(self, dialog: QDialog) -> None:
        dialog.adjustSize()
        size = dialog.size()
        screen = QGuiApplication.screenAt(self.sticker_center_global()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        frame = self.frameGeometry()
        margin = 14
        candidates = [
            QPoint(frame.left() - size.width() - margin, frame.top() + max(0, (frame.height() - size.height()) // 2)),
            QPoint(frame.right() + margin, frame.top() + max(0, (frame.height() - size.height()) // 2)),
            QPoint(frame.left() + max(0, (frame.width() - size.width()) // 2), frame.top() - size.height() - margin),
            QPoint(frame.left() + max(0, (frame.width() - size.width()) // 2), frame.bottom() + margin),
        ]
        for candidate in candidates:
            rect = QRect(candidate, size)
            if area.contains(rect):
                dialog.move(candidate)
                return
        x = min(max(candidates[0].x(), area.left() + margin), area.right() - size.width() - margin)
        y = min(max(candidates[0].y(), area.top() + margin), area.bottom() - size.height() - margin)
        dialog.move(x, y)

    def fetch_agent_reply(self, prompt: str) -> None:
        reply = call_agent(self.config, prompt)
        if self.config.memory_enabled:
            try:
                append_memory_turn(prompt, reply)
            except Exception:
                pass
        self.agent_signals.reply_ready.emit(reply)

    def set_pet_size(self, size: int) -> None:
        old_center = self.sticker_center_global()
        self.pet_size = max(96, min(420, size))
        self.resize(*self.window_dimensions())
        self.move(old_center - self.sticker_rect().center().toPoint())
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.draw_bubble(painter)
        self.draw_drop_effect(painter)
        self.draw_drag_effect(painter)

        sticker = self.sticker_rect()
        visual = self.pixmap_fit_rect(sticker)
        center = sticker.center()
        scale = self.scale()
        painter.save()
        painter.translate(center.x(), center.y())
        painter.scale(scale, scale)
        painter.translate(-center.x(), -center.y())
        painter.drawPixmap(visual, self.pixmap, QRectF(self.pixmap.rect()))
        painter.restore()

        self.draw_action_buttons(painter)

    def sticker_rect(self) -> QRectF:
        usable_width = max(self.pet_size, self.width() - self.action_rail_width())
        return QRectF((usable_width - self.pet_size) / 2, self.bubble_height + 6, self.pet_size, self.pet_size)

    def pixmap_fit_rect(self, target: QRectF) -> QRectF:
        image_ratio = self.pixmap.width() / max(1, self.pixmap.height())
        target_ratio = target.width() / max(1.0, target.height())
        if image_ratio >= target_ratio:
            width = target.width()
            height = width / image_ratio
        else:
            height = target.height()
            width = height * image_ratio
        return QRectF(target.center().x() - width / 2, target.center().y() - height / 2, width, height)

    def effect_intensity(self, until: float, duration: float) -> float:
        remaining = until - time.monotonic()
        if remaining <= 0:
            return 0.0
        return min(1.0, max(0.0, remaining / max(0.01, duration)))

    def drop_zone_rect(self) -> QRectF:
        zone = self.sticker_rect().united(self.chat_button_rect()).united(self.settings_button_rect()).united(self.quit_button_rect())
        expanded = zone.adjusted(-DROP_HOTZONE_PAD, -DROP_HOTZONE_PAD, DROP_HOTZONE_PAD, DROP_HOTZONE_PAD)
        return expanded.intersected(QRectF(self.rect()))

    def draw_drop_effect(self, painter: QPainter) -> None:
        intensity = 1.0 if self.drop_hover else self.effect_intensity(self.drop_effect_until, DROP_EFFECT_DURATION)
        if intensity <= 0:
            return
        zone = self.drop_zone_rect()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(0.72 * intensity)
        painter.setPen(QPen(QColor(76, 201, 240, 210), 2.2))
        painter.setBrush(QColor(20, 184, 166, 34))
        painter.drawRoundedRect(zone, 22, 22)
        painter.setPen(QPen(QColor(255, 255, 255, 230), 1.8))
        icon = QRectF(zone.center().x() - 20, zone.top() + 13, 40, 28)
        painter.drawRoundedRect(icon, 5, 5)
        painter.drawLine(QPointF(icon.left() + 8, icon.top() - 5), QPointF(icon.right() - 8, icon.top() - 5))
        painter.drawLine(QPointF(icon.center().x(), icon.top() - 6), QPointF(icon.center().x(), icon.center().y() + 5))
        painter.drawLine(QPointF(icon.center().x(), icon.center().y() + 5), QPointF(icon.center().x() - 7, icon.center().y() - 2))
        painter.drawLine(QPointF(icon.center().x(), icon.center().y() + 5), QPointF(icon.center().x() + 7, icon.center().y() - 2))
        painter.restore()

    def draw_drag_effect(self, painter: QPainter) -> None:
        intensity = 1.0 if self.dragging else self.effect_intensity(self.drag_effect_until, DRAG_RELEASE_EFFECT_DURATION)
        if intensity <= 0:
            return
        sticker = self.sticker_rect().adjusted(-7, -7, 7, 7)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(0.45 * intensity)
        painter.setPen(QPen(QColor(125, 92, 255, 190), 2.0))
        painter.setBrush(QColor(14, 165, 233, 24))
        painter.drawEllipse(sticker)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1.2))
        painter.drawArc(sticker.adjusted(7, 7, -7, -7), 25 * 16, 145 * 16)
        painter.restore()

    def draw_bubble(self, painter: QPainter) -> None:
        now = time.monotonic()
        if now >= self.message_until:
            return

        remaining = self.message_until - now
        opacity = min(1.0, max(0.0, remaining / 0.22)) if remaining < 0.22 else 1.0
        painter.save()
        painter.setOpacity(opacity)

        bubble_width = min(max(BUBBLE_MIN_WIDTH, self.bubble_width), self.width() - 12)
        body = QRectF((self.width() - bubble_width) / 2, BUBBLE_TOP, bubble_width, self.bubble_body_height)
        tail = QPainterPath()
        tail.moveTo(self.width() / 2 - 10, body.bottom() - 1)
        tail.lineTo(self.width() / 2, body.bottom() + 14)
        tail.lineTo(self.width() / 2 + 10, body.bottom() - 1)
        tail.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 66))
        radius = min(18, max(8, self.bubble_body_height / 3))
        painter.drawRoundedRect(body.translated(0, 3), radius, radius)
        painter.drawPath(tail.translated(0, 3))

        painter.setBrush(QColor(25, 30, 38, 238))
        painter.setPen(QPen(QColor(255, 255, 255, 75), 1.2))
        painter.drawRoundedRect(body, radius, radius)
        painter.drawPath(tail)

        painter.setFont(self.bubble_font())
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            body.adjusted(BUBBLE_TEXT_PAD_X, 0, -BUBBLE_TEXT_PAD_X, -2),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.current_message,
        )
        painter.restore()

    def draw_action_buttons(self, painter: QPainter) -> None:
        self.draw_chat_button(painter)
        self.draw_settings_button(painter)
        self.draw_quit_button(painter)

    def draw_round_button_base(self, painter: QPainter, button: QRectF, *, pressed: bool) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if pressed:
            bg = QColor(55, 122, 255, 238)
            shadow = QColor(0, 0, 0, 80)
        else:
            bg = QColor(25, 30, 38, 226)
            shadow = QColor(0, 0, 0, 58)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(button.translated(0, 2))
        painter.setBrush(bg)
        painter.drawEllipse(button)
        painter.restore()

    def draw_chat_button(self, painter: QPainter) -> None:
        button = self.chat_button_rect()
        self.draw_round_button_base(painter, button, pressed=self.chat_button_pressed)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255, 235), max(1.7, button.width() * 0.055)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        bubble = button.adjusted(button.width() * 0.24, button.height() * 0.25, -button.width() * 0.22, -button.height() * 0.34)
        radius = max(3.0, button.width() * 0.10)
        painter.drawRoundedRect(bubble, radius, radius)

        tail = QPainterPath()
        tail.moveTo(bubble.left() + bubble.width() * 0.30, bubble.bottom() - 0.5)
        tail.lineTo(bubble.left() + bubble.width() * 0.22, bubble.bottom() + button.height() * 0.16)
        tail.lineTo(bubble.left() + bubble.width() * 0.48, bubble.bottom() - 0.5)
        painter.drawPath(tail)
        painter.restore()

    def draw_settings_button(self, painter: QPainter) -> None:
        button = self.settings_button_rect()
        self.draw_round_button_base(painter, button, pressed=self.settings_button_pressed)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = button.center()
        outer = button.width() * 0.22
        inner = button.width() * 0.08
        painter.setPen(QPen(QColor(255, 255, 255, 235), max(1.6, button.width() * 0.052)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, outer, outer)
        painter.drawEllipse(center, inner, inner)
        for index in range(8):
            angle = math.tau * index / 8
            start = QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer)
            end = QPointF(center.x() + math.cos(angle) * outer * 1.34, center.y() + math.sin(angle) * outer * 1.34)
            painter.drawLine(start, end)
        painter.restore()

    def draw_quit_button(self, painter: QPainter) -> None:
        button = self.quit_button_rect()
        self.draw_round_button_base(painter, button, pressed=self.quit_button_pressed)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pad = button.width() * 0.32
        painter.setPen(QPen(QColor(255, 255, 255, 235), max(1.8, button.width() * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(button.left() + pad, button.top() + pad), QPointF(button.right() - pad, button.bottom() - pad))
        painter.drawLine(QPointF(button.right() - pad, button.top() + pad), QPointF(button.left() + pad, button.bottom() - pad))
        painter.restore()

    @staticmethod
    def cover_source_rect(pixmap: QPixmap, target: QRectF) -> QRectF:
        image_ratio = pixmap.width() / max(1, pixmap.height())
        target_ratio = target.width() / max(1.0, target.height())
        if image_ratio > target_ratio:
            source_width = pixmap.height() * target_ratio
            x = (pixmap.width() - source_width) / 2
            return QRectF(x, 0, source_width, pixmap.height())
        source_height = pixmap.width() / target_ratio
        y = (pixmap.height() - source_height) / 2
        return QRectF(0, y, pixmap.width(), source_height)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {APP_NAME}.")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE, help="PNG/JPG image for the desktop mentor")
    parser.add_argument("--message", default=DEFAULT_CLICK_MESSAGE, help="bubble text shown on touch/click")
    parser.add_argument("--size", type=int, default=150, help="portrait size in pixels")
    parser.add_argument("--quit-after", type=float, default=0.0, help="exit after N seconds")
    parser.add_argument("--self-test", action="store_true", help="load the app without opening a visible pet")
    parser.add_argument("--make-icon", nargs=2, metavar=("SOURCE_IMAGE", "OUTPUT_ICO"), help="convert a PNG/image file to ICO")
    parser.add_argument("--ensure-default-icon", action="store_true", help="generate assets/desktop_mentor.ico from the default mentor PNG")
    parser.add_argument("--force-icon", action="store_true", help="regenerate ICO even when the target is newer")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.make_icon:
        icon_path = convert_image_to_ico(Path(args.make_icon[0]), Path(args.make_icon[1]), force=True)
        print(json.dumps({"ok": True, "icon": str(icon_path)}, ensure_ascii=False))
        return 0
    if args.ensure_default_icon:
        icon_path = ensure_default_icon(force=args.force_icon)
        print(json.dumps({"ok": True, "icon": str(icon_path)}, ensure_ascii=False))
        return 0

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(APP_STYLESHEET)
    image_path = args.image.expanduser().resolve()

    pet = DesktopMentorPet(image_path, args.message, args.size)
    if args.self_test:
        result = {
            "ok": True,
            "image": str(pet.image_path),
            "image_size": [pet.pixmap.width(), pet.pixmap.height()],
            "click_message": pet.config.click_message,
            "idle_message": pet.config.idle_message,
            "drop_message": pet.config.drop_message,
            "message_seconds": pet.config.message_seconds,
            "idle_mode": pet.config.idle_mode,
            "memory_enabled": pet.config.memory_enabled,
            "memory_path": str(memory_path()),
            "todos_path": str(todos_path()),
            "icon": pet.config.icon_path,
            "icon_error": pet.icon_error,
            "window_size": [pet.width(), pet.height()],
            "config_path": str(pet.config_path),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    pet.show()
    pet.raise_()
    if args.quit_after > 0:
        QTimer.singleShot(int(args.quit_after * 1000), QApplication.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
