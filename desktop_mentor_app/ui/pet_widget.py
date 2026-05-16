"""Transparent desktop pet widget."""
from __future__ import annotations

import math
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, QTimer, Qt, QEvent, Signal
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QIcon, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap, QFontMetrics
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QWidget

from ..agent_client import append_memory_turn, call_agent, compact_text
from ..assets import DEFAULT_IMAGE, convert_image_to_ico, ensure_default_icon, icon_cache_path_for_image
from ..config_store import config_path, load_config, save_config, save_config_directory
from ..constants import (
    ACTION_BUTTON_GAP,
    ACTION_BUTTON_MAX_SIZE,
    ACTION_BUTTON_MIN_SIZE,
    ACTION_BUTTON_OUTER_PAD,
    ACTION_BUTTON_STICKER_GAP,
    BUBBLE_BODY_MAX_HEIGHT,
    BUBBLE_BODY_MIN_HEIGHT,
    BUBBLE_BOTTOM_PAD,
    BUBBLE_MAX_WIDTH,
    BUBBLE_MIN_HEIGHT,
    BUBBLE_MIN_WIDTH,
    BUBBLE_TAIL_HEIGHT,
    BUBBLE_TEXT_PAD_X,
    BUBBLE_TEXT_PAD_Y,
    BUBBLE_TOP,
    CHAT_BUTTON_MAX_SIZE,
    CHAT_BUTTON_MIN_SIZE,
    DEFAULT_CLICK_MESSAGE,
    DEFAULT_DROP_MESSAGE,
    DEFAULT_IDLE_MESSAGE,
    DEFAULT_IDLE_SECONDS,
    DEFAULT_MESSAGE_SECONDS,
    DRAG_RELEASE_EFFECT_DURATION,
    DROP_EFFECT_DURATION,
    DROP_HOTZONE_PAD,
    IDLE_CHECK_INTERVAL_MS,
    IDLE_MODE_FULLSCREEN,
    MAX_BUBBLE_TEXT_CHARS,
    MAX_MESSAGE_SECONDS,
    MIN_IDLE_SECONDS,
    MIN_MESSAGE_SECONDS,
    TODO_CHECK_INTERVAL_MS,
    WINDOW_PAD,
)
from ..drop_context import collect_drop_context, compose_prompt_with_drop_context
from ..idle_detector import system_idle_seconds
from ..todo_store import load_todos, save_todos
from .dialogs import APP_STYLESHEET, ChatDialog, FullScreenIdleAlert, SettingsDialog, TextViewDialog, TodoDialog


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
        self.show_bubble(f"{self.config.drop_message or DEFAULT_DROP_MESSAGE} 下次对话可选择加载这些上下文。", duration=self.message_duration())
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
        settings = QAction("设置", self)
        quit_action = QAction("退出", self)
        ask_files = QAction("只问文件", self)
        show_files = QAction("文件摘要", self)
        clear_files = QAction("清除文件上下文", self)
        bigger = QAction("放大", self)
        smaller = QAction("缩小", self)
        reset = QAction("回到右下角", self)
        chat.triggered.connect(self.open_chat)
        todo_action.triggered.connect(self.open_todos)
        settings.triggered.connect(self.open_settings)
        quit_action.triggered.connect(QApplication.quit)
        ask_files.triggered.connect(self.ask_about_dropped_files)
        show_files.triggered.connect(self.open_drop_summary)
        clear_files.triggered.connect(self.clear_drop_context)
        bigger.triggered.connect(lambda: self.set_pet_size(self.pet_size + 28))
        smaller.triggered.connect(lambda: self.set_pet_size(self.pet_size - 28))
        reset.triggered.connect(self.move_to_lower_right)
        menu.addAction(chat)
        menu.addAction(settings)
        menu.addAction(todo_action)
        menu.addAction(quit_action)
        if self.last_drop_context:
            menu.addSeparator()
            menu.addAction(ask_files)
            menu.addAction(show_files)
            menu.addAction(clear_files)
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

    def drop_context_hint(self) -> str:
        if not self.last_drop_context:
            return ""
        count = len(self.last_drop_paths)
        names = [Path(path).name or str(path) for path in self.last_drop_paths[:3]]
        suffix = f"：{'、'.join(names)}" if names else ""
        if count > 3:
            suffix += f" 等 {count} 项"
        return f"文件上下文{suffix}"

    def open_chat(self) -> None:
        self.mark_interaction()
        dialog = ChatDialog(self, self.drop_context_hint())
        self.position_dialog_near_pet(dialog)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if dialog.drop_context_was_removed():
            self.last_drop_paths = []
            self.last_drop_context = ""
        if not accepted:
            return
        user_prompt = dialog.text()
        if not user_prompt:
            return
        drop_context = self.last_drop_context if dialog.use_drop_context() else ""
        prompt = compose_prompt_with_drop_context(user_prompt, drop_context)
        self.show_bubble("导师处理中。", duration=min(1.8, self.message_duration()))
        thread = threading.Thread(target=self.fetch_agent_reply, args=(prompt, user_prompt), daemon=True)
        thread.start()

    def ask_about_dropped_files(self) -> None:
        self.mark_interaction()
        if not self.last_drop_context:
            self.show_bubble("还没有拖入文件。", duration=self.message_duration())
            return
        user_prompt = "请先概括这些文件/文件夹的内容，再指出最值得我下一步处理的事项。"
        prompt = compose_prompt_with_drop_context(user_prompt, self.last_drop_context)
        self.show_bubble("导师正在看文件。", duration=min(1.8, self.message_duration()))
        thread = threading.Thread(target=self.fetch_agent_reply, args=(prompt, "只问文件"), daemon=True)
        thread.start()

    def open_drop_summary(self) -> None:
        self.mark_interaction()
        if not self.last_drop_context:
            self.show_bubble("还没有拖入文件。", duration=self.message_duration())
            return
        dialog = TextViewDialog("文件摘要", self.last_drop_context, self)
        self.position_dialog_near_pet(dialog)
        dialog.exec()

    def clear_drop_context(self) -> None:
        self.mark_interaction()
        self.last_drop_paths = []
        self.last_drop_context = ""
        self.show_bubble("文件上下文已清除。", duration=self.message_duration())

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

    def fetch_agent_reply(self, prompt: str, memory_prompt: str | None = None) -> None:
        reply = call_agent(self.config, prompt)
        if self.config.memory_enabled:
            try:
                append_memory_turn(memory_prompt or prompt, reply)
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
