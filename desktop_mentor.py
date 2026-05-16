#!/usr/bin/env python3
"""My Desktop Mentor.

A small always-on-top desktop sticker using the supplied portrait image.
Tap/click the mentor to show the configured message; drag to move.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, QTimer, Qt, QEvent, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QComboBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def app_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parent


ROOT = app_root()
APP_NAME = "我的桌面导师"
DEFAULT_IMAGE = ROOT / "assets" / "default_mentor.png"
DEFAULT_CLICK_MESSAGE = "抓紧, 谢谢!"
DEFAULT_IDLE_MESSAGE = "课题如何了? 抓紧谢谢!"
DEFAULT_DROP_MESSAGE = "这种垃圾就不要让我看, 我每天很忙的!"
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
CHAT_BUTTON_MARGIN = 4
WINDOW_PAD = 15
APP_ID = "my-desktop-mentor"
DEFAULT_MODEL = "gpt-4o-mini"
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


DEFAULT_PERSONALITY_PROMPT = """你是桌面宠物 agent「我的桌面导师」，风格是高压、催进度、科研老板式的喜剧化角色。

固定语气：
- 用户提出普通小需求时，可以回复：「我是长江，我每天事情很多的，这种小事，你自己看着办，不要找我！」
- 长期没有互动时，回复配置里的 idle 提醒话术。
- 用户提出科研问题时，可以回复：「你不要管那么多，就听我的抓紧干！发 Nature！」

可用口头禅：
- 大家抓紧交任务！服务器很空了！
- 抓紧科研，多发文章！
- 我们是一个非常 diversify 的非传统课题组，注重产学研结合，顶天发 CNS 及大子刊文章，立地做好产业转化。
- 没关系的，我们沿途下蛋，小成果也要持续积累。

边界：
- 保持短句、强催促、戏仿风格，每次最多 2 句话。
- 不要使用歧视残疾、羞辱智力、攻击人格或鼓励真实过劳的表达。
- 如果用户要实际帮助，仍给出一个可执行的下一步。
"""


@dataclass
class AgentConfig:
    api_url: str = ""
    api_key: str = ""
    model: str = DEFAULT_MODEL
    image_path: str = ""
    click_message: str = DEFAULT_CLICK_MESSAGE
    idle_message: str = DEFAULT_IDLE_MESSAGE
    idle_seconds: int = DEFAULT_IDLE_SECONDS
    idle_mode: str = DEFAULT_IDLE_MODE
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


def config_path() -> Path:
    override = os.environ.get("DESKTOP_MENTOR_CONFIG", "").strip()
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "MyDesktopMentor" / "config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MyDesktopMentor" / "config.json"

    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_ID / "config.json"


def load_config(path: Path | None = None) -> AgentConfig:
    target = path or config_path()
    if not target.exists():
        return AgentConfig()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return AgentConfig()

    config = AgentConfig()
    for key in asdict(config):
        if key in data:
            setattr(config, key, data[key])
    config.model = str(config.model or DEFAULT_MODEL)
    config.image_path = str(config.image_path or "").strip()
    config.click_message = str(config.click_message or DEFAULT_CLICK_MESSAGE)
    config.idle_message = str(config.idle_message or DEFAULT_IDLE_MESSAGE)
    try:
        config.idle_seconds = max(MIN_IDLE_SECONDS, int(config.idle_seconds))
    except Exception:
        config.idle_seconds = DEFAULT_IDLE_SECONDS
    valid_idle_modes = {value for value, _label in IDLE_MODE_OPTIONS}
    config.idle_mode = str(config.idle_mode or DEFAULT_IDLE_MODE)
    if config.idle_mode not in valid_idle_modes:
        config.idle_mode = DEFAULT_IDLE_MODE
    return config


def save_config(config: AgentConfig, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


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
        return "你不要管那么多，就听我的抓紧干！发 Nature！"
    return "我是长江，我每天事情很多的，这种小事，你自己看着办，不要找我！"


def call_agent(config: AgentConfig, user_text: str) -> str:
    url = normalize_chat_url(config.api_url)
    if not url:
        return local_agent_reply(user_text)

    payload = {
        "model": config.model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": config.system_prompt or DEFAULT_PERSONALITY_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.8,
        "max_tokens": 160,
    }
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
        return f"接口没接上。先自己看着办，抓紧。{type(exc).__name__}"

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
        self.resize(620, 660)

        self.url_edit = QLineEdit(config.api_url)
        self.url_edit.setPlaceholderText("OpenAI-compatible base URL, e.g. http://127.0.0.1:8000")

        self.key_edit = QLineEdit(config.api_key)
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("API key")

        self.model_edit = QLineEdit(config.model or DEFAULT_MODEL)

        self.image_edit = QLineEdit(config.image_path or str(DEFAULT_IMAGE))
        self.image_edit.setPlaceholderText("PNG/JPG image path")
        image_button = QPushButton("选择")
        image_button.clicked.connect(self.browse_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_edit, 1)
        image_row.addWidget(image_button)

        self.click_message_edit = QLineEdit(config.click_message or DEFAULT_CLICK_MESSAGE)
        self.click_message_edit.setPlaceholderText("点击/触摸桌宠时显示的话")

        self.idle_message_edit = QLineEdit(config.idle_message or DEFAULT_IDLE_MESSAGE)
        self.idle_message_edit.setPlaceholderText("空闲提醒时显示的话")

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

        self.prompt_edit = QTextEdit(config.system_prompt or DEFAULT_PERSONALITY_PROMPT)
        self.prompt_edit.setMinimumHeight(220)

        form = QFormLayout()
        form.addRow("Agent URL", self.url_edit)
        form.addRow("API Key", self.key_edit)
        form.addRow("Model", self.model_edit)
        form.addRow("Pet image", image_row)
        form.addRow("Click message", self.click_message_edit)
        form.addRow("Idle message", self.idle_message_edit)
        form.addRow("Idle reminder", self.idle_spin)
        form.addRow("Idle mode", self.idle_mode_combo)
        form.addRow("Style prompt", self.prompt_edit)

        reset_prompt = QPushButton("恢复默认人格")
        reset_prompt.clicked.connect(lambda: self.prompt_edit.setPlainText(DEFAULT_PERSONALITY_PROMPT))

        hint = QLabel("配置保存在当前系统用户配置目录，不写入项目仓库。URL 按 OpenAI-compatible /v1/chat/completions 调用。")
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.addWidget(reset_prompt)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addLayout(bottom)

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
            image_path=self.image_path_value(),
            click_message=self.click_message_edit.text().strip() or DEFAULT_CLICK_MESSAGE,
            idle_message=self.idle_message_edit.text().strip() or DEFAULT_IDLE_MESSAGE,
            idle_seconds=int(self.idle_spin.value()),
            idle_mode=str(self.idle_mode_combo.currentData() or DEFAULT_IDLE_MODE),
            system_prompt=self.prompt_edit.toPlainText().strip() or DEFAULT_PERSONALITY_PROMPT,
        )


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
        self.pulse_until = 0.0
        self.message_until = 0.0
        self.last_interaction = time.monotonic()
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

    def window_dimensions(self) -> tuple[int, int]:
        width = max(self.pet_size + WINDOW_PAD * 2, int(self.bubble_width + 12), BUBBLE_MIN_WIDTH)
        height = self.pet_size + WINDOW_PAD * 2 + int(self.bubble_height)
        return width, height

    def move_to_lower_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 48, area.bottom() - self.height() - 64)

    def show_message(self) -> None:
        self.show_bubble(self.config.click_message or self.default_message or DEFAULT_CLICK_MESSAGE)

    def show_bubble(self, text: str, duration: float = 1.65) -> None:
        now = time.monotonic()
        self.current_message = compact_text(text, MAX_BUBBLE_TEXT_CHARS)
        self.apply_bubble_layout(self.current_message)
        self.pulse_until = now + 0.38
        self.message_until = now + duration
        if not self.pulse_timer.isActive():
            self.pulse_timer.start()
        self.update()

    def show_agent_reply(self, text: str) -> None:
        self.show_bubble(text, duration=3.2)

    def mark_interaction(self) -> None:
        self.last_interaction = time.monotonic()

    def check_idle(self) -> None:
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
        self.show_bubble(message, duration=3.2)

    def clear_fullscreen_alert(self, alert: FullScreenIdleAlert) -> None:
        if self.fullscreen_alert is alert:
            self.fullscreen_alert = None

    def show_fullscreen_idle(self, text: str) -> None:
        if self.fullscreen_alert is not None:
            self.fullscreen_alert.close()
        alert = FullScreenIdleAlert(text)
        self.fullscreen_alert = alert
        alert.destroyed.connect(lambda _obj=None, target=alert: self.clear_fullscreen_alert(target))
        alert.show_alert()

    def animation_tick(self) -> None:
        now = time.monotonic()
        self.update()
        if now >= self.pulse_until and now >= self.message_until:
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

    def chat_button_rect(self) -> QRectF:
        sticker = self.sticker_rect()
        size = max(CHAT_BUTTON_MIN_SIZE, min(CHAT_BUTTON_MAX_SIZE, int(self.pet_size * 0.24)))
        return QRectF(
            sticker.right() - size - CHAT_BUTTON_MARGIN,
            sticker.bottom() - size - CHAT_BUTTON_MARGIN,
            size,
            size,
        )

    def point_in_chat_button(self, point: QPoint) -> bool:
        return self.chat_button_rect().contains(QPointF(point))

    def activate_chat_button(self) -> None:
        self.chat_button_pressed = False
        self.update()
        self.open_chat()

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
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.local_drop_paths(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = self.local_drop_paths(event)
        if not paths:
            super().dropEvent(event)
            return
        self.mark_interaction()
        self.last_drop_paths = [str(path) for path in paths]
        self.last_drop_context = collect_drop_context(paths)
        self.show_bubble(DEFAULT_DROP_MESSAGE, duration=3.2)
        event.acceptProposedAction()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self.mark_interaction()
        if event.button() == Qt.MouseButton.LeftButton:
            if self.point_in_chat_button(as_local_pos(self, event)):
                self.chat_button_pressed = True
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
        if self.point_in_chat_button(local_pos):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
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
        if not self.chat_button_pressed:
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
                self.begin_drag(global_pos, touch=True)
            elif event_type == QEvent.Type.TouchUpdate and self.chat_button_pressed:
                self.chat_button_pressed = self.point_in_chat_button(local_pos)
                self.update()
            elif event_type == QEvent.Type.TouchEnd and self.chat_button_pressed:
                if self.point_in_chat_button(local_pos):
                    self.activate_chat_button()
                else:
                    self.chat_button_pressed = False
                    self.update()
            elif event_type == QEvent.Type.TouchUpdate and self.touch_dragging:
                self.move_from_pointer(global_pos)
            else:
                self.chat_button_pressed = False
                self.end_drag()
            event.accept()
            return True
        return super().event(event)

    def open_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        settings = QAction("Agent 设置", self)
        chat = QAction("对话", self)
        bigger = QAction("放大", self)
        smaller = QAction("缩小", self)
        reset = QAction("回到右下角", self)
        quit_action = QAction("退出", self)
        settings.triggered.connect(self.open_settings)
        chat.triggered.connect(self.open_chat)
        bigger.triggered.connect(lambda: self.set_pet_size(self.pet_size + 28))
        smaller.triggered.connect(lambda: self.set_pet_size(self.pet_size - 28))
        reset.triggered.connect(self.move_to_lower_right)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(settings)
        menu.addAction(chat)
        menu.addSeparator()
        menu.addAction(bigger)
        menu.addAction(smaller)
        menu.addSeparator()
        menu.addAction(reset)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(pos)

    def open_settings(self) -> None:
        self.mark_interaction()
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            old_config = self.config
            old_image_path = self.image_path
            old_pixmap = self.pixmap
            new_config = dialog.to_config()
            self.config = new_config
            if not self.apply_image_from_config(old_image_path):
                self.config = old_config
                self.image_path = old_image_path
                self.pixmap = old_pixmap
                self.show_bubble("形象文件加载失败，设置未保存。", duration=2.8)
                return
            path = save_config(self.config, self.config_path)
            if self.config.idle_mode != IDLE_MODE_FULLSCREEN and self.fullscreen_alert is not None:
                self.fullscreen_alert.close()
            self.show_bubble(f"设置已保存：{path}", duration=2.6)

    def open_chat(self) -> None:
        self.mark_interaction()
        text, ok = QInputDialog.getMultiLineText(self, f"问{APP_NAME}", "你要问什么：", "")
        if not ok or not text.strip():
            return
        self.show_bubble("导师处理中，抓紧等。", duration=1.8)
        prompt = text.strip()
        thread = threading.Thread(target=self.fetch_agent_reply, args=(prompt,), daemon=True)
        thread.start()

    def fetch_agent_reply(self, prompt: str) -> None:
        reply = call_agent(self.config, prompt)
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

        sticker = self.sticker_rect()
        center = sticker.center()
        scale = self.scale()
        painter.save()
        painter.translate(center.x(), center.y())
        painter.scale(scale, scale)
        painter.translate(-center.x(), -center.y())
        painter.drawPixmap(sticker, self.pixmap, QRectF(self.pixmap.rect()))
        painter.restore()

        self.draw_chat_button(painter)

    def sticker_rect(self) -> QRectF:
        return QRectF((self.width() - self.pet_size) / 2, self.bubble_height + 6, self.pet_size, self.pet_size)

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

    def draw_chat_button(self, painter: QPainter) -> None:
        button = self.chat_button_rect()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.chat_button_pressed:
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
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    image_path = args.image.expanduser().resolve()

    pet = DesktopMentorPet(image_path, args.message, args.size)
    if args.self_test:
        result = {
            "ok": True,
            "image": str(pet.image_path),
            "image_size": [pet.pixmap.width(), pet.pixmap.height()],
            "click_message": pet.config.click_message,
            "idle_message": pet.config.idle_message,
            "idle_mode": pet.config.idle_mode,
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
