"""Transparent desktop pet widget."""
from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, QTimer, Qt, QEvent, Signal
from PySide6.QtGui import QContextMenuEvent, QFont, QFontMetrics, QGuiApplication, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QDialog, QWidget

from ..config.store import config_path, load_config
from ..core.assets import DEFAULT_IMAGE, convert_image_to_ico, ensure_default_icon, icon_cache_path_for_image
from ..core.task_runner import AsyncTaskRunner
from ..model_client.agent import compact_text
from ..pet.chat_manager import PetConversationService
from ..pet.idle_manager import IdleManager
from ..pet.sticker_manager import StickerAnimationManager
from ..pet.todo_manager import PetTodoService
from ..state.conversations import ensure_active_session, get_session
from ..tools.types import ControlPlan
from ..constants import (
    DEFAULT_CLICK_MESSAGE,
    DEFAULT_IDLE_MESSAGE,
    DEFAULT_IDLE_SECONDS,
    DEFAULT_MESSAGE_SECONDS,
    MAX_PET_SIZE,
    IDLE_CHECK_INTERVAL_MS,
    IDLE_MODE_FULLSCREEN,
    MAX_MESSAGE_SECONDS,
    MIN_IDLE_SECONDS,
    MIN_MESSAGE_SECONDS,
    MIN_PET_SIZE,
    STICKER_ACTION_ALERT,
    STICKER_ACTION_ERROR,
    STICKER_ACTION_SPEAKING,
    STICKER_ACTION_TAP,
    TODO_CHECK_INTERVAL_MS,
)
from .tokens import (
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
    DROP_HOTZONE_PAD,
    FULLSCREEN_ALERT_DURATION_MS,
    MAX_BUBBLE_TEXT_CHARS,
    TODO_BUBBLE_GAP,
    TODO_BUBBLE_MAX_HEIGHT,
    TODO_BUBBLE_MAX_VISIBLE,
    TODO_BUBBLE_MAX_WIDTH,
    TODO_BUBBLE_MIN_HEIGHT,
    TODO_BUBBLE_MIN_WIDTH,
    TODO_BUBBLE_TEXT_PAD_X,
    TODO_BUBBLE_TEXT_PAD_Y,
    TODO_BUBBLE_TOP,
    WINDOW_PAD,
)
from ..pet.stickers import normalize_sticker_sets
from .dialogs import ChatDialog, FullScreenIdleAlert, TextViewDialog
from .pet_dialog_coordinator import PetDialogCoordinator
from .pet_interaction_controller import PetInteractionController
from .pet_painter import PetPainter
from .tray_controller import PetTrayController

LOGGER = logging.getLogger(__name__)


class AgentSignals(QObject):
    reply_ready = Signal(str, str)
    error_ready = Signal(str, str)
    # PySide6 limitation: object signals are used for dataclass payloads.
    control_plan_ready = Signal(object, str, str, str)


class DesktopMentorPet(QWidget):
    def __init__(
        self,
        image_path: Path,
        message: str,
        size: int,
        *,
        idle_manager: IdleManager | None = None,
        task_runner: AsyncTaskRunner | None = None,
        chat_service: PetConversationService | None = None,
        todo_service: PetTodoService | None = None,
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.default_message = message
        self.current_message = message
        self.pet_size = max(MIN_PET_SIZE, min(MAX_PET_SIZE, size))
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
        self.sticker_animation = StickerAnimationManager(self.pixmap)
        self.fullscreen_alert: FullScreenIdleAlert | None = None
        self.chat_dialog: ChatDialog | None = None
        self.tray_controller = PetTrayController(self)
        self.icon_error = self.refresh_window_icon()

        self.dragging = False
        self.native_drag_active = False
        self.drag_offset = QPoint()
        self.drag_start = QPoint()
        self.last_drag_pos = QPoint()
        self.touch_dragging = False
        self.touch_start_pos = QPoint()
        self.touch_long_press_menu_opened = False
        self.last_drop_context = ""
        self.last_drop_paths: list[str] = []
        self.todo_bubbles: list[dict[str, object]] = []
        self.pending_control_plans: dict[str, tuple[ControlPlan, str, str]] = {}
        self.todo_stack_height = 0
        self.chat_button_pressed = False
        self.settings_button_pressed = False
        self.quit_button_pressed = False
        self.drop_hover = False
        self.drop_effect_until = 0.0
        self.drag_effect_until = 0.0
        self.context_menu_active = False
        self.last_context_menu_closed_at = 0.0
        self.pulse_until = 0.0
        self.message_until = 0.0
        self.idle_manager = idle_manager or IdleManager()
        self.hovering = False
        self.agent_signals = AgentSignals()
        self.agent_signals.reply_ready.connect(self.show_agent_reply)
        self.agent_signals.error_ready.connect(self.show_agent_error)
        self.agent_signals.control_plan_ready.connect(self.show_agent_control_request)
        self.task_runner = task_runner or AsyncTaskRunner(self)
        self.chat_service = chat_service or PetConversationService()
        self.todo_service = todo_service or PetTodoService()
        self.dialog_coordinator = PetDialogCoordinator(self)
        self.interaction_controller = PetInteractionController(self)
        self.pet_painter = PetPainter(self)
        self.task_runner.task_error.connect(lambda text: self.agent_signals.error_ready.emit(text, ""))
        self.destroyed.connect(lambda _obj=None: self.task_runner.shutdown())

        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(16)
        self.pulse_timer.timeout.connect(self.animation_tick)
        self.reload_sticker_sets()
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
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(*self.window_dimensions())
        self.move_to_lower_right()
        self.tray_controller.setup()

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
        self.sticker_animation.set_base_pixmap(pixmap)
        self.update()
        return True

    @property
    def current_action(self) -> str:
        return self.sticker_animation.current_action

    def reload_sticker_sets(self) -> list[str]:
        self.config.sticker_sets = normalize_sticker_sets(self.config.sticker_sets)
        invalid_paths = self.sticker_animation.reload(self.config.sticker_sets)
        if self.sticker_animation.has_multi_frame_action():
            self.ensure_animation_timer()
        self.update()
        return invalid_paths

    def sticker_frame_counts(self) -> dict[str, int]:
        return self.sticker_animation.frame_counts()

    def action_frames(self, action: str) -> list[QPixmap]:
        return self.sticker_animation.action_frames(action)

    def current_sticker_pixmap(self) -> QPixmap:
        return self.sticker_animation.current_pixmap()

    def action_source_rect(self, action: str) -> QRectF:
        return self.sticker_animation.action_source_rect(action)

    def current_sticker_source_rect(self) -> QRectF:
        return self.sticker_animation.current_source_rect()

    def action_union_source_rect(self, frames: list[QPixmap]) -> QRectF:
        return self.sticker_animation.action_union_source_rect(frames)

    def pixmap_content_rect(self, pixmap: QPixmap) -> QRectF:
        return self.sticker_animation.pixmap_content_rect(pixmap)

    def ensure_animation_timer(self) -> None:
        if not self.pulse_timer.isActive():
            self.pulse_timer.start()

    def sticker_animation_speed(self) -> float:
        return self.sticker_animation.animation_speed(self.config.sticker_animation_speed)

    def sticker_frame_interval_seconds(self) -> float:
        return self.sticker_animation.frame_interval_seconds(self.config.sticker_animation_speed)

    def play_action(self, action: str, *, duration: float = 0.0, loop: bool = True, restart: bool = True) -> None:
        self.sticker_animation.play_action(action, duration=duration, loop=loop, restart=restart)
        self.ensure_animation_timer()
        self.update()

    def update_active_action(self, now: float) -> None:
        self.sticker_animation.update_active_action(now)

    def advance_sticker_frame(self, now: float) -> None:
        self.sticker_animation.advance_frame(now, self.config.sticker_animation_speed)

    def has_active_sticker_animation(self, now: float) -> bool:
        return self.sticker_animation.has_active_animation(now)

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
                icon = QIcon(str(icon_path))
                self.setWindowIcon(icon)
                self.update_tray_icon(icon)
                return ""

            raw_icon = str(self.config.icon_path or "").strip()
            if raw_icon and Path(raw_icon).expanduser().exists():
                icon = QIcon(str(Path(raw_icon).expanduser()))
                self.setWindowIcon(icon)
                self.update_tray_icon(icon)
                return ""
            self.config.icon_path = ""
            return ""
        except Exception as exc:
            self.config.icon_path = ""
            return f"{type(exc).__name__}: {exc}"

    def update_tray_icon(self, icon: QIcon | None = None) -> None:
        self.tray_controller.update_icon(icon)

    @property
    def tray_icon(self) -> object | None:
        return self.tray_controller.tray_icon

    @property
    def tray_menu(self) -> object | None:
        return self.tray_controller.tray_menu

    def window_dimensions(self) -> tuple[int, int]:
        rail_width = self.action_rail_width()
        width = max(
            self.pet_size + WINDOW_PAD * 2 + rail_width + DROP_HOTZONE_PAD * 2,
            int(self.bubble_width + 12),
            int(self.todo_bubble_width() + 12) if self.todo_bubbles else 0,
            BUBBLE_MIN_WIDTH,
        )
        height = self.pet_size + WINDOW_PAD * 2 + int(self.bubble_height) + self.todo_stack_height + DROP_HOTZONE_PAD
        return width, height

    def move_to_lower_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 48, area.bottom() - self.height() - 64)

    def show_message(self) -> None:
        self.show_bubble(
            self.config.click_message or self.default_message or DEFAULT_CLICK_MESSAGE,
            duration=self.message_duration(),
            action=STICKER_ACTION_TAP,
        )

    def message_duration(self) -> float:
        try:
            return max(MIN_MESSAGE_SECONDS, min(MAX_MESSAGE_SECONDS, float(self.config.message_seconds)))
        except Exception:
            return DEFAULT_MESSAGE_SECONDS

    def show_bubble(self, text: str, duration: float = 1.65, *, action: str | None = STICKER_ACTION_SPEAKING) -> None:
        now = time.monotonic()
        self.current_message = compact_text(text, MAX_BUBBLE_TEXT_CHARS)
        self.apply_bubble_layout(self.current_message)
        self.pulse_until = now + 0.38
        self.message_until = now + duration
        if action is not None:
            self.play_action(action, duration=duration, loop=True)
        else:
            self.ensure_animation_timer()
        self.update()

    def start_visual_effect(self, duration: float) -> None:
        self.ensure_animation_timer()
        self.update()

    def show_agent_reply(self, text: str, session_id: str = "") -> None:
        self.show_bubble(text, duration=self.message_duration(), action=STICKER_ACTION_SPEAKING)
        if self.chat_dialog is not None:
            self.refresh_chat_dialog_sessions()
            if self.chat_dialog.waiting_for_reply:
                self.chat_dialog.set_waiting(False)
        if (
            self.chat_dialog is not None
            and (not session_id or self.chat_dialog.active_session_id == session_id)
        ):
            self.chat_dialog.add_assistant_message(text)

    def show_agent_error(self, text: str, session_id: str = "") -> None:
        self.show_bubble(text, duration=self.message_duration(), action=STICKER_ACTION_ERROR)
        if self.chat_dialog is not None:
            self.refresh_chat_dialog_sessions()
            if self.chat_dialog.waiting_for_reply:
                self.chat_dialog.set_waiting(False)
        if (
            self.chat_dialog is not None
            and (not session_id or self.chat_dialog.active_session_id == session_id)
        ):
            self.chat_dialog.add_assistant_message(text)

    def show_agent_control_request(
        self,
        plan: object,
        assistant_text: str,
        source_text: str,
        session_id: str,
    ) -> None:
        self.dialog_coordinator.show_agent_control_request(plan, assistant_text, source_text, session_id)

    def mark_interaction(self) -> None:
        self.idle_manager.mark_interaction()

    def check_idle(self) -> None:
        if self.idle_manager.is_suppressed():
            return
        if self.todo_bubbles:
            return
        if self.todo_service.has_due_items():
            return
        idle_seconds = max(MIN_IDLE_SECONDS, int(self.config.idle_seconds or DEFAULT_IDLE_SECONDS))
        idle_for = self.idle_manager.idle_seconds()
        if idle_for < idle_seconds:
            return
        self.show_idle_reminder()

    def show_idle_reminder(self) -> None:
        message = self.config.idle_message or DEFAULT_IDLE_MESSAGE
        if self.config.idle_mode == IDLE_MODE_FULLSCREEN:
            self.show_fullscreen_idle(message)
            return
        self.show_bubble(message, duration=self.message_duration(), action=STICKER_ACTION_ALERT)

    def open_idle_diagnostics(self) -> None:
        self.mark_interaction()
        report = self.idle_manager.diagnostics()
        text = json.dumps(report, ensure_ascii=False, indent=2)
        dialog = TextViewDialog("Idle 检测诊断", text)
        self.position_dialog_near_pet(dialog)
        dialog.activate_for_input()
        dialog.exec()

    def clear_fullscreen_alert(self, alert: FullScreenIdleAlert) -> None:
        if self.fullscreen_alert is alert:
            self.fullscreen_alert = None

    def show_fullscreen_idle(self, text: str) -> None:
        if self.fullscreen_alert is not None:
            self.fullscreen_alert.close()
        self.play_action(STICKER_ACTION_ALERT, duration=max(FULLSCREEN_ALERT_DURATION_MS / 1000, self.message_duration()), loop=True)
        alert = FullScreenIdleAlert(text, int(self.message_duration() * 1000))
        self.fullscreen_alert = alert
        alert.destroyed.connect(lambda _obj=None, target=alert: self.clear_fullscreen_alert(target))
        alert.show_alert()

    def animation_tick(self) -> None:
        now = time.monotonic()
        self.update_active_action(now)
        self.advance_sticker_frame(now)
        self.update()
        if (
            now >= self.pulse_until
            and now >= self.message_until
            and now >= self.drag_effect_until
            and now >= self.drop_effect_until
            and not self.drop_hover
            and not self.dragging
        ):
            self.reset_bubble_layout()
            if not self.has_active_sticker_animation(now):
                self.pulse_timer.stop()

    @staticmethod
    def bubble_font() -> QFont:
        font = QFont()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    @staticmethod
    def todo_bubble_font() -> QFont:
        font = QFont()
        font.setPointSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def visible_todo_bubbles(self) -> list[dict[str, object]]:
        return self.todo_bubbles[-TODO_BUBBLE_MAX_VISIBLE:]

    def todo_bubble_width(self) -> int:
        if not self.todo_bubbles:
            return TODO_BUBBLE_MIN_WIDTH
        font_metrics = QFontMetrics(self.todo_bubble_font())
        max_width = TODO_BUBBLE_MIN_WIDTH
        for bubble in self.visible_todo_bubbles():
            text = self.todo_bubble_text(bubble)
            max_width = max(max_width, min(TODO_BUBBLE_MAX_WIDTH, font_metrics.horizontalAdvance(text) + TODO_BUBBLE_TEXT_PAD_X * 2))
        return int(max(TODO_BUBBLE_MIN_WIDTH, min(TODO_BUBBLE_MAX_WIDTH, max_width)))

    def todo_bubble_text(self, bubble: dict[str, object]) -> str:
        count = sum(1 for item in self.todo_bubbles if str(item["todo_id"]) == str(bubble["todo_id"]))
        prefix = f"待办提醒 x{count}" if count > 1 else "待办提醒"
        return f"{prefix}: {bubble['text']}"

    def todo_bubble_rects(self) -> list[tuple[dict[str, object], QRectF]]:
        if not self.todo_bubbles:
            return []
        font_metrics = QFontMetrics(self.todo_bubble_font())
        width = min(TODO_BUBBLE_MAX_WIDTH, max(TODO_BUBBLE_MIN_WIDTH, self.todo_bubble_width()))
        x = (self.width() - width) / 2
        y = TODO_BUBBLE_TOP
        rects: list[tuple[dict[str, object], QRectF]] = []
        for bubble in self.visible_todo_bubbles():
            text_rect = font_metrics.boundingRect(
                0,
                0,
                int(width - TODO_BUBBLE_TEXT_PAD_X * 2),
                2000,
                int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
                self.todo_bubble_text(bubble),
            )
            height = int(max(TODO_BUBBLE_MIN_HEIGHT, min(TODO_BUBBLE_MAX_HEIGHT, text_rect.height() + TODO_BUBBLE_TEXT_PAD_Y * 2)))
            rect = QRectF(x, y, width, height)
            rects.append((bubble, rect))
            y += height + TODO_BUBBLE_GAP
        return rects

    def recalculate_todo_stack_layout(self) -> None:
        if not self.todo_bubbles:
            new_height = 0
        else:
            rects = self.todo_bubble_rects()
            new_height = int(rects[-1][1].bottom() + TODO_BUBBLE_GAP) if rects else 0
        if new_height == self.todo_stack_height:
            return
        self.todo_stack_height = new_height
        self.resize_preserving_sticker()
        self.keep_window_visible()

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

    def keep_window_visible(self) -> None:
        screen = QGuiApplication.screenAt(self.sticker_center_global()) or QGuiApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        frame = self.frameGeometry()
        x = min(max(frame.left(), area.left() + 4), area.right() - max(80, frame.width()) + 4)
        y = min(max(frame.top(), area.top() + 4), area.bottom() - max(80, frame.height()) + 4)
        if x != frame.left() or y != frame.top():
            self.move(x, y)

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
        self.interaction_controller.begin_drag(global_pos, touch=touch)

    def try_start_system_move(self) -> bool:
        return self.interaction_controller.try_start_system_move()

    def move_from_pointer(self, global_pos: QPoint) -> None:
        self.interaction_controller.move_from_pointer(global_pos)

    def follow_drag_pointer(self) -> None:
        self.interaction_controller.follow_drag_pointer()

    def end_drag(self) -> None:
        self.interaction_controller.end_drag()

    def action_button_size(self) -> int:
        return self.interaction_controller.action_button_size()

    def action_rail_width(self) -> int:
        return self.interaction_controller.action_rail_width()

    def action_button_rects(self) -> tuple[QRectF, QRectF, QRectF]:
        return self.interaction_controller.action_button_rects()

    def settings_button_rect(self) -> QRectF:
        return self.interaction_controller.settings_button_rect()

    def chat_button_rect(self) -> QRectF:
        return self.interaction_controller.chat_button_rect()

    def quit_button_rect(self) -> QRectF:
        return self.interaction_controller.quit_button_rect()

    def point_in_chat_button(self, point: QPoint) -> bool:
        return self.interaction_controller.point_in_chat_button(point)

    def point_in_settings_button(self, point: QPoint) -> bool:
        return self.interaction_controller.point_in_settings_button(point)

    def point_in_quit_button(self, point: QPoint) -> bool:
        return self.interaction_controller.point_in_quit_button(point)

    def point_in_action_button(self, point: QPoint) -> bool:
        return self.interaction_controller.point_in_action_button(point)

    def todo_id_at_point(self, point: QPoint) -> str:
        local_point = QPointF(point)
        for bubble, rect in self.todo_bubble_rects():
            if rect.contains(local_point):
                return str(bubble["todo_id"])
        return ""

    def todo_repeat_seconds(self) -> int:
        return self.todo_service.repeat_seconds(self.config.todo_repeat_seconds)

    def add_todo_bubble(self, todo: dict[str, object]) -> None:
        self.todo_bubbles.append(
            {
                "todo_id": str(todo["id"]),
                "text": compact_text(str(todo["text"]), 180),
                "created_ts": int(time.time()),
            }
        )
        self.recalculate_todo_stack_layout()
        self.raise_()
        self.pulse_until = time.monotonic() + 0.38
        if not self.pulse_timer.isActive():
            self.pulse_timer.start()
        self.play_action(STICKER_ACTION_ALERT, duration=max(2.0, self.message_duration()), loop=True)
        self.update()

    def acknowledge_todo_reminder(self, todo_id: str) -> None:
        if not todo_id:
            return
        self.mark_interaction()
        self.todo_service.acknowledge(todo_id)
        self.todo_bubbles = [bubble for bubble in self.todo_bubbles if str(bubble["todo_id"]) != todo_id]
        self.recalculate_todo_stack_layout()
        self.idle_manager.suppress_for(6.0)
        self.update()

    def sync_todo_bubbles_with_store(self) -> None:
        todo_ids = self.todo_service.active_ids()
        if not self.todo_bubbles:
            return
        self.todo_bubbles = [bubble for bubble in self.todo_bubbles if str(bubble["todo_id"]) in todo_ids]
        self.recalculate_todo_stack_layout()
        self.update()

    def activate_chat_button(self) -> None:
        self.interaction_controller.activate_chat_button()

    def activate_settings_button(self) -> None:
        self.interaction_controller.activate_settings_button()

    def activate_quit_button(self) -> None:
        self.interaction_controller.activate_quit_button()

    def open_touch_menu(self) -> None:
        self.interaction_controller.open_touch_menu()

    @staticmethod
    def local_drop_paths(event) -> list[Path]:
        return PetInteractionController.local_drop_paths(event)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self.interaction_controller.drag_enter_event(event):
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.interaction_controller.drag_move_event(event):
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.interaction_controller.drag_leave_event(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        if self.interaction_controller.drop_event(event):
            return
        super().dropEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self.interaction_controller.mouse_press_event(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self.interaction_controller.mouse_move_event(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self.interaction_controller.mouse_release_event(event):
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # type: ignore[override]
        self.interaction_controller.context_menu_event(event)

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
            return self.interaction_controller.touch_event(event)
        return super().event(event)

    def open_menu(self, pos: QPoint) -> None:
        self.interaction_controller.open_menu(pos)

    def open_settings(self) -> None:
        self.dialog_coordinator.open_settings()

    def open_todos(self) -> None:
        self.dialog_coordinator.open_todos()

    def check_todos(self) -> None:
        due = self.todo_service.pop_due_reminders(repeat_seconds=self.todo_repeat_seconds())
        if not due:
            return
        for todo in due:
            self.add_todo_bubble(todo)
        if self.fullscreen_alert is not None:
            self.fullscreen_alert.close()
        self.idle_manager.suppress_for(max(8.0, self.message_duration() + 3.0))

    def drop_context_hint(self) -> str:
        return self.dialog_coordinator.drop_context_hint()

    def open_chat(self) -> None:
        self.dialog_coordinator.open_chat()

    def clear_chat_dialog(self, dialog: ChatDialog) -> None:
        self.dialog_coordinator.clear_chat_dialog(dialog)

    def refresh_chat_dialog_sessions(self) -> None:
        self.dialog_coordinator.refresh_chat_dialog_sessions()

    def load_chat_session_in_dialog(self, session_id: str) -> None:
        self.dialog_coordinator.load_chat_session_in_dialog(session_id)

    def create_chat_session_from_dialog(self) -> None:
        self.dialog_coordinator.create_chat_session_from_dialog()

    def clear_chat_history_from_dialog(self, session_id: str) -> None:
        self.dialog_coordinator.clear_chat_history_from_dialog(session_id)

    def session_for_context_policy(
        self,
        user_prompt: str,
        session_id: str,
        use_conversation_context: bool,
    ):
        return self.dialog_coordinator.session_for_context_policy(user_prompt, session_id, use_conversation_context)

    def show_user_message_for_session(self, user_prompt: str, session_id: str) -> None:
        self.dialog_coordinator.show_user_message_for_session(user_prompt, session_id)

    def handle_chat_message(
        self,
        user_prompt: str,
        use_drop_context: bool,
        session_id: str,
        use_conversation_context: bool,
    ) -> None:
        self.dialog_coordinator.handle_chat_message(user_prompt, use_drop_context, session_id, use_conversation_context)

    def handle_control_plan(self, plan: ControlPlan, user_prompt: str, session_id: str) -> None:
        self.dialog_coordinator.handle_control_plan(plan, user_prompt, session_id)

    def request_control_authorization(self, plan: ControlPlan, user_prompt: str, session_id: str) -> None:
        self.dialog_coordinator.request_control_authorization(plan, user_prompt, session_id)

    def approve_control_plan(self, plan_id: str) -> None:
        self.dialog_coordinator.approve_control_plan(plan_id)

    def cancel_control_plan(self, plan_id: str) -> None:
        self.dialog_coordinator.cancel_control_plan(plan_id)

    def queue_control_reply(self, plan: ControlPlan, memory_prompt: str, session_id: str) -> None:
        self.dialog_coordinator.queue_control_reply(plan, memory_prompt, session_id)

    async def fetch_control_reply(self, plan: ControlPlan, memory_prompt: str, session_id: str) -> None:
        await self.dialog_coordinator.fetch_control_reply(plan, memory_prompt, session_id)

    def ask_about_dropped_files(self) -> None:
        self.dialog_coordinator.ask_about_dropped_files()

    def open_drop_summary(self) -> None:
        self.dialog_coordinator.open_drop_summary()

    def clear_drop_context(self) -> None:
        self.dialog_coordinator.clear_drop_context()

    def position_dialog_near_pet(self, dialog: QDialog) -> None:
        self.dialog_coordinator.position_dialog_near_pet(dialog)

    async def fetch_agent_reply(
        self,
        prompt: str,
        memory_prompt: str | None = None,
        session_id: str = "",
        use_conversation_context: bool = True,
    ) -> None:
        result = await self.chat_service.fetch_agent_reply(
            self.config,
            prompt,
            memory_prompt=memory_prompt,
            session_id=session_id,
            use_conversation_context=use_conversation_context,
        )
        if result.control_plan is not None:
            self.agent_signals.control_plan_ready.emit(
                result.control_plan,
                result.text,
                result.control_source_text,
                result.session_id,
            )
            return
        if result.is_error:
            self.agent_signals.error_ready.emit(result.text, result.session_id)
            return
        self.agent_signals.reply_ready.emit(result.text, result.session_id)

    def set_pet_size(self, size: int) -> None:
        old_center = self.sticker_center_global()
        self.pet_size = max(MIN_PET_SIZE, min(MAX_PET_SIZE, size))
        self.resize(*self.window_dimensions())
        self.move(old_center - self.sticker_rect().center().toPoint())
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        self.pet_painter.paint()

    def sticker_rect(self) -> QRectF:
        usable_width = max(self.pet_size, self.width() - self.action_rail_width())
        return QRectF((usable_width - self.pet_size) / 2, self.todo_stack_height + self.bubble_height + 6, self.pet_size, self.pet_size)

    def pixmap_fit_rect(self, target: QRectF, source_rect: QRectF | None = None) -> QRectF:
        return self.pet_painter.pixmap_fit_rect(target, source_rect)

    def current_sticker_visual_rect(self) -> QRectF:
        return self.pet_painter.current_sticker_visual_rect()

    def effect_intensity(self, until: float, duration: float) -> float:
        return self.pet_painter.effect_intensity(until, duration)

    def drop_zone_rect(self) -> QRectF:
        return self.pet_painter.drop_zone_rect()

    @staticmethod
    def cover_source_rect(pixmap: QPixmap, target: QRectF) -> QRectF:
        return PetPainter.cover_source_rect(pixmap, target)
