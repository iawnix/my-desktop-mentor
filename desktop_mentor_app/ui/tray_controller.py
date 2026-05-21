"""System tray integration for the pet widget."""
from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from ..constants import APP_NAME
from .dialog_chrome import prepare_modern_menu


class TrayPet(Protocol):
    def windowIcon(self) -> QIcon:
        """Return the current window icon."""

    def show(self) -> None:
        """Show the pet widget."""

    def hide(self) -> None:
        """Hide the pet widget."""

    def raise_(self) -> None:
        """Raise the pet widget."""

    def activateWindow(self) -> None:
        """Activate the pet widget."""

    def keep_window_visible(self) -> None:
        """Keep the pet inside the current screen."""

    def open_chat(self) -> None:
        """Open chat dialog."""

    def open_todos(self) -> None:
        """Open todo dialog."""

    def open_settings(self) -> None:
        """Open settings dialog."""

    def move_to_lower_right(self) -> None:
        """Move pet to the lower-right screen area."""


class PetTrayController(QObject):
    def __init__(self, pet: QWidget) -> None:
        super().__init__(pet)
        self._widget = pet
        self.pet = cast(TrayPet, pet)
        self.tray_icon: QSystemTrayIcon | None = None
        self.tray_menu: QMenu | None = None

    def setup(self) -> None:
        if self.tray_icon is not None or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self.pet.windowIcon(), self._widget)
        self.tray_icon.setToolTip(APP_NAME)
        self.tray_menu = self._build_menu()
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.handle_activation)
        self.tray_icon.show()

    def update_icon(self, icon: QIcon | None = None) -> None:
        if self.tray_icon is None:
            return
        self.tray_icon.setIcon(icon or self.pet.windowIcon())

    def restore_pet(self) -> None:
        self.pet.show()
        self.pet.keep_window_visible()
        self.pet.raise_()
        self.pet.activateWindow()

    def handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        }:
            self.restore_pet()

    def _build_menu(self) -> QMenu:
        menu = prepare_modern_menu(QMenu(self._widget))
        show_action = QAction("显示桌宠", self._widget)
        hide_action = QAction("隐藏桌宠", self._widget)
        chat_action = QAction("对话", self._widget)
        todo_action = QAction("待办", self._widget)
        settings_action = QAction("设置", self._widget)
        reset_action = QAction("回到右下角", self._widget)
        quit_action = QAction("退出", self._widget)
        show_action.triggered.connect(self.restore_pet)
        hide_action.triggered.connect(self.pet.hide)
        chat_action.triggered.connect(self.pet.open_chat)
        todo_action.triggered.connect(self.pet.open_todos)
        settings_action.triggered.connect(self.pet.open_settings)
        reset_action.triggered.connect(self.pet.move_to_lower_right)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(show_action)
        menu.addAction(hide_action)
        menu.addSeparator()
        menu.addAction(chat_action)
        menu.addAction(todo_action)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(reset_action)
        menu.addAction(quit_action)
        return menu
