"""Pointer, drag/drop, button, and context-menu behavior for the pet widget."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QContextMenuEvent, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu

from ..constants import (
    DEFAULT_CLICK_MESSAGE,
    DEFAULT_DROP_MESSAGE,
    STICKER_ACTION_DRAG,
    STICKER_ACTION_DROP_FILE,
)
from ..tools.drop_context import collect_drop_context
from .dialog_chrome import prepare_modern_menu
from .pointer_events import as_context_menu_pos, as_global_pos, as_local_pos
from .tokens import (
    ACTION_BUTTON_GAP,
    ACTION_BUTTON_MAX_SIZE,
    ACTION_BUTTON_MIN_SIZE,
    ACTION_BUTTON_OUTER_PAD,
    ACTION_BUTTON_STICKER_GAP,
    DRAG_RELEASE_EFFECT_DURATION,
    DROP_EFFECT_DURATION,
)


class PetInteractionController:
    def __init__(self, pet: Any) -> None:
        self.pet = pet

    def begin_drag(self, global_pos: QPoint, *, touch: bool = False) -> None:
        pet = self.pet
        pet.mark_interaction()
        pet.dragging = True
        pet.native_drag_active = False
        pet.touch_dragging = touch
        pet.drag_start = global_pos
        pet.last_drag_pos = global_pos
        pet.drag_offset = global_pos - pet.frameGeometry().topLeft()
        pet.raise_()
        pet.native_drag_active = self.try_start_system_move()
        pet.drag_effect_until = time.monotonic() + DRAG_RELEASE_EFFECT_DURATION
        pet.setCursor(Qt.CursorShape.ClosedHandCursor)
        pet.start_visual_effect(DRAG_RELEASE_EFFECT_DURATION)
        pet.show_bubble(
            pet.config.click_message or pet.default_message or DEFAULT_CLICK_MESSAGE,
            duration=pet.message_duration(),
            action=None,
        )
        pet.play_action(STICKER_ACTION_DRAG, loop=True)
        if touch:
            pet.touch_start_pos = global_pos
            pet.touch_long_press_menu_opened = False
            pet.touch_menu_timer.start(620)
        if touch and not pet.drag_follow_timer.isActive():
            pet.drag_follow_timer.start()

    def try_start_system_move(self) -> bool:
        pet = self.pet
        if not QGuiApplication.platformName().lower().startswith("wayland"):
            return False
        handle = pet.windowHandle()
        if handle is None:
            return False
        try:
            return bool(handle.startSystemMove())
        except Exception:
            return False

    def move_from_pointer(self, global_pos: QPoint) -> None:
        pet = self.pet
        if pet.touch_dragging and pet.touch_menu_timer.isActive():
            delta = global_pos - pet.touch_start_pos
            if abs(delta.x()) + abs(delta.y()) > 10:
                pet.touch_menu_timer.stop()
        pet.last_drag_pos = global_pos
        if pet.native_drag_active:
            return
        pet.move(global_pos - pet.drag_offset)

    def follow_drag_pointer(self) -> None:
        pet = self.pet
        if not pet.dragging or not pet.touch_dragging:
            pet.drag_follow_timer.stop()
            return
        if pet.native_drag_active:
            return
        pointer = pet.last_drag_pos
        if not pointer.isNull():
            pet.move(pointer - pet.drag_offset)

    def end_drag(self) -> None:
        pet = self.pet
        pet.dragging = False
        pet.native_drag_active = False
        pet.touch_dragging = False
        pet.drag_follow_timer.stop()
        pet.touch_menu_timer.stop()
        pet.drag_effect_until = time.monotonic() + DRAG_RELEASE_EFFECT_DURATION
        pet.setCursor(Qt.CursorShape.OpenHandCursor if pet.hovering else Qt.CursorShape.ArrowCursor)
        pet.play_action(STICKER_ACTION_DRAG, duration=DRAG_RELEASE_EFFECT_DURATION, loop=True)
        pet.start_visual_effect(DRAG_RELEASE_EFFECT_DURATION)

    def action_button_size(self) -> int:
        pet = self.pet
        return max(ACTION_BUTTON_MIN_SIZE, min(ACTION_BUTTON_MAX_SIZE, int(pet.pet_size * 0.24)))

    def action_rail_width(self) -> int:
        return self.action_button_size() + ACTION_BUTTON_STICKER_GAP + ACTION_BUTTON_OUTER_PAD

    def action_button_rects(self) -> tuple[QRectF, QRectF, QRectF]:
        pet = self.pet
        sticker = pet.sticker_rect()
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
        pet = self.pet
        pet.chat_button_pressed = False
        pet.update()
        pet.open_chat()

    def activate_settings_button(self) -> None:
        pet = self.pet
        pet.settings_button_pressed = False
        pet.update()
        pet.open_settings()

    def activate_quit_button(self) -> None:
        pet = self.pet
        pet.quit_button_pressed = False
        pet.update()
        QApplication.quit()

    def open_touch_menu(self) -> None:
        pet = self.pet
        if not pet.touch_dragging:
            return
        pet.touch_long_press_menu_opened = True
        self.end_drag()
        self.open_menu(pet.last_drag_pos if not pet.last_drag_pos.isNull() else pet.mapToGlobal(pet.rect().center()))

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

    def drag_enter_event(self, event) -> bool:
        pet = self.pet
        if self.local_drop_paths(event):
            pet.raise_()
            pet.drop_hover = True
            pet.drop_effect_until = time.monotonic() + DROP_EFFECT_DURATION
            pet.setCursor(Qt.CursorShape.DragCopyCursor)
            pet.play_action(STICKER_ACTION_DROP_FILE, loop=True)
            pet.start_visual_effect(DROP_EFFECT_DURATION)
            event.acceptProposedAction()
            return True
        return False

    def drag_move_event(self, event) -> bool:
        pet = self.pet
        if self.local_drop_paths(event):
            pet.drop_hover = True
            pet.drop_effect_until = time.monotonic() + DROP_EFFECT_DURATION
            pet.play_action(STICKER_ACTION_DROP_FILE, loop=True)
            pet.start_visual_effect(DROP_EFFECT_DURATION)
            event.acceptProposedAction()
            return True
        return False

    def drag_leave_event(self, event) -> None:
        pet = self.pet
        pet.drop_hover = False
        if not pet.dragging:
            pet.unsetCursor()
        pet.drop_effect_until = time.monotonic() + 0.18
        pet.play_action(STICKER_ACTION_DROP_FILE, duration=0.18, loop=True)
        pet.start_visual_effect(0.18)
        event.accept()

    def drop_event(self, event) -> bool:
        pet = self.pet
        paths = self.local_drop_paths(event)
        if not paths:
            return False
        pet.mark_interaction()
        pet.drop_hover = False
        pet.drop_effect_until = time.monotonic() + DROP_EFFECT_DURATION
        pet.unsetCursor()
        pet.last_drop_paths = [str(path) for path in paths]
        pet.last_drop_context = collect_drop_context(paths)
        pet.show_bubble(
            f"{pet.config.drop_message or DEFAULT_DROP_MESSAGE} 下次对话可选择加载这些上下文。",
            duration=pet.message_duration(),
            action=STICKER_ACTION_DROP_FILE,
        )
        event.acceptProposedAction()
        return True

    def mouse_press_event(self, event: QMouseEvent) -> bool:
        pet = self.pet
        pet.mark_interaction()
        if event.button() == Qt.MouseButton.LeftButton:
            local_pos = as_local_pos(pet, event)
            todo_id = pet.todo_id_at_point(local_pos)
            if todo_id:
                pet.acknowledge_todo_reminder(todo_id)
                event.accept()
                return True
            if self.point_in_chat_button(local_pos):
                pet.chat_button_pressed = True
                pet.update()
                event.accept()
                return True
            if self.point_in_settings_button(local_pos):
                pet.settings_button_pressed = True
                pet.update()
                event.accept()
                return True
            if self.point_in_quit_button(local_pos):
                pet.quit_button_pressed = True
                pet.update()
                event.accept()
                return True
            self.begin_drag(as_global_pos(pet, event))
            event.accept()
            return True
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return True
        return False

    def mouse_move_event(self, event: QMouseEvent) -> bool:
        pet = self.pet
        local_pos = as_local_pos(pet, event)
        if pet.settings_button_pressed:
            pet.settings_button_pressed = self.point_in_settings_button(local_pos)
            pet.update()
            event.accept()
            return True
        if pet.quit_button_pressed:
            pet.quit_button_pressed = self.point_in_quit_button(local_pos)
            pet.update()
            event.accept()
            return True
        if pet.chat_button_pressed:
            pet.chat_button_pressed = self.point_in_chat_button(local_pos)
            pet.update()
            event.accept()
            return True
        if pet.dragging and not pet.touch_dragging:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                self.end_drag()
                event.accept()
                return True
            self.move_from_pointer(as_global_pos(pet, event))
            event.accept()
            return True
        if pet.dragging and pet.touch_dragging:
            event.accept()
            return True
        if self.point_in_action_button(local_pos):
            pet.setCursor(Qt.CursorShape.PointingHandCursor)
        elif pet.sticker_rect().contains(QPointF(local_pos)):
            pet.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            pet.unsetCursor()
        return False

    def mouse_release_event(self, event: QMouseEvent) -> bool:
        pet = self.pet
        if event.button() == Qt.MouseButton.LeftButton and pet.settings_button_pressed:
            if self.point_in_settings_button(as_local_pos(pet, event)):
                self.activate_settings_button()
            else:
                pet.settings_button_pressed = False
                pet.update()
            event.accept()
            return True
        if event.button() == Qt.MouseButton.LeftButton and pet.quit_button_pressed:
            if self.point_in_quit_button(as_local_pos(pet, event)):
                self.activate_quit_button()
            else:
                pet.quit_button_pressed = False
                pet.update()
            event.accept()
            return True
        if event.button() == Qt.MouseButton.LeftButton and pet.chat_button_pressed:
            if self.point_in_chat_button(as_local_pos(pet, event)):
                self.activate_chat_button()
            else:
                pet.chat_button_pressed = False
                pet.update()
            event.accept()
            return True
        if event.button() == Qt.MouseButton.LeftButton and pet.dragging and not pet.touch_dragging:
            self.end_drag()
            event.accept()
            return True
        if event.button() == Qt.MouseButton.RightButton:
            pet.mark_interaction()
            self.open_menu(as_global_pos(pet, event))
            event.accept()
            return True
        return False

    def context_menu_event(self, event: QContextMenuEvent) -> bool:
        pet = self.pet
        pet.mark_interaction()
        if event.reason() == QContextMenuEvent.Reason.Mouse:
            event.accept()
            return True
        self.open_menu(as_context_menu_pos(pet, event))
        event.accept()
        return True

    def touch_event(self, event) -> bool:
        pet = self.pet
        event_type = event.type()
        points = event.points()
        if not points:
            return True
        point = points[0]
        local_pos = as_local_pos(pet, point)
        global_pos = as_global_pos(pet, point)

        if event_type == QEvent.Type.TouchBegin:
            todo_id = pet.todo_id_at_point(local_pos)
            if todo_id:
                pet.acknowledge_todo_reminder(todo_id)
                event.accept()
                return True
            if self.point_in_chat_button(local_pos):
                pet.chat_button_pressed = True
                pet.update()
                event.accept()
                return True
            if self.point_in_settings_button(local_pos):
                pet.settings_button_pressed = True
                pet.update()
                event.accept()
                return True
            if self.point_in_quit_button(local_pos):
                pet.quit_button_pressed = True
                pet.update()
                event.accept()
                return True
            self.begin_drag(global_pos, touch=True)
        elif event_type == QEvent.Type.TouchUpdate and pet.settings_button_pressed:
            pet.settings_button_pressed = self.point_in_settings_button(local_pos)
            pet.update()
        elif event_type == QEvent.Type.TouchUpdate and pet.chat_button_pressed:
            pet.chat_button_pressed = self.point_in_chat_button(local_pos)
            pet.update()
        elif event_type == QEvent.Type.TouchUpdate and pet.quit_button_pressed:
            pet.quit_button_pressed = self.point_in_quit_button(local_pos)
            pet.update()
        elif event_type == QEvent.Type.TouchEnd and pet.settings_button_pressed:
            if self.point_in_settings_button(local_pos):
                self.activate_settings_button()
            else:
                pet.settings_button_pressed = False
                pet.update()
        elif event_type == QEvent.Type.TouchEnd and pet.chat_button_pressed:
            if self.point_in_chat_button(local_pos):
                self.activate_chat_button()
            else:
                pet.chat_button_pressed = False
                pet.update()
        elif event_type == QEvent.Type.TouchEnd and pet.quit_button_pressed:
            if self.point_in_quit_button(local_pos):
                self.activate_quit_button()
            else:
                pet.quit_button_pressed = False
                pet.update()
        elif event_type == QEvent.Type.TouchUpdate and pet.touch_dragging:
            self.move_from_pointer(global_pos)
        else:
            pet.settings_button_pressed = False
            pet.chat_button_pressed = False
            pet.quit_button_pressed = False
            self.end_drag()
        event.accept()
        return True

    def open_menu(self, pos: QPoint) -> None:
        pet = self.pet
        now = time.monotonic()
        if pet.context_menu_active or now - pet.last_context_menu_closed_at < 0.2:
            return
        pet.context_menu_active = True
        menu = prepare_modern_menu(QMenu(pet))
        chat = QAction("对话", pet)
        todo_action = QAction("待办", pet)
        settings = QAction("设置", pet)
        idle_diag = QAction("Idle 诊断", pet)
        quit_action = QAction("退出", pet)
        ask_files = QAction("只问文件", pet)
        show_files = QAction("文件摘要", pet)
        clear_files = QAction("清除文件上下文", pet)
        bigger = QAction("放大", pet)
        smaller = QAction("缩小", pet)
        reset = QAction("回到右下角", pet)
        chat.triggered.connect(pet.open_chat)
        todo_action.triggered.connect(pet.open_todos)
        settings.triggered.connect(pet.open_settings)
        idle_diag.triggered.connect(pet.open_idle_diagnostics)
        quit_action.triggered.connect(QApplication.quit)
        ask_files.triggered.connect(pet.ask_about_dropped_files)
        show_files.triggered.connect(pet.open_drop_summary)
        clear_files.triggered.connect(pet.clear_drop_context)
        bigger.triggered.connect(lambda: pet.set_pet_size(pet.pet_size + 28))
        smaller.triggered.connect(lambda: pet.set_pet_size(pet.pet_size - 28))
        reset.triggered.connect(pet.move_to_lower_right)
        menu.addAction(chat)
        menu.addAction(settings)
        menu.addAction(todo_action)
        menu.addAction(idle_diag)
        menu.addAction(quit_action)
        if pet.last_drop_context:
            menu.addSeparator()
            menu.addAction(ask_files)
            menu.addAction(show_files)
            menu.addAction(clear_files)
        menu.addSeparator()
        menu.addAction(bigger)
        menu.addAction(smaller)
        menu.addSeparator()
        menu.addAction(reset)
        try:
            menu.exec(pos)
        finally:
            pet.context_menu_active = False
            pet.last_context_menu_closed_at = time.monotonic()
