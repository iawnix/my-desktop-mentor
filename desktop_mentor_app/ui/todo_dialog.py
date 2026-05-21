"""Todo reminder editor dialog."""
from __future__ import annotations

import time

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.assets import TODO_BADGE_IMAGE
from ..state.todos import format_due_time, load_todos_from_items
from .dialog_chrome import (
    activate_input_window,
    add_resize_grip,
    enable_text_input,
    make_hairline,
    mark_button,
    setup_modern_dialog,
    style_dialog_buttons,
    styled_label,
    title_bar,
    transparent_frame,
)


class TodoDialog(QDialog):
    def __init__(self, todos: list[dict[str, object]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("待办提醒")
        setup_modern_dialog(self)
        self.resize(620, 500)
        self.setMinimumSize(480, 380)
        self.todos = load_todos_from_items(todos)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        badge = QLabel()
        pixmap = QPixmap(str(TODO_BADGE_IMAGE))
        if not pixmap.isNull():
            badge.setPixmap(pixmap.scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(badge)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        title_box.addWidget(styled_label("待办", "dialogTitle"))
        title_box.addWidget(styled_label("点击提醒泡泡后移除；未点击会按设置间隔再次提醒。", "dialogSubtitle", True))
        header.addLayout(title_box, 1)
        header.addStretch(1)

        self.todo_edit = QLineEdit()
        self.todo_edit.setPlaceholderText("要提醒的事情")
        enable_text_input(self.todo_edit)

        self.due_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(30 * 60))
        self.due_edit.setCalendarPopup(False)
        self.due_edit.setKeyboardTracking(True)
        self.due_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.due_edit.setFixedWidth(190)

        add_button = QPushButton("添加")
        mark_button(add_button, "primaryButton")
        add_button.clicked.connect(self.add_todo)

        editor = QHBoxLayout()
        editor.setContentsMargins(0, 0, 0, 0)
        editor.setSpacing(8)
        editor.addWidget(self.todo_edit, 1)
        editor.addWidget(self.due_edit)
        editor.addWidget(add_button)

        self.todo_list = QListWidget()
        self.todo_list.setMinimumHeight(220)

        remove_button = QPushButton("删除选中")
        mark_button(remove_button, "dangerButton")
        remove_button.clicked.connect(self.remove_selected)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        style_dialog_buttons(buttons)
        buttons.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(10)
        bottom.addWidget(remove_button)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 15, 16, 16)
        panel_layout.setSpacing(13)
        panel_layout.addLayout(header)
        panel_layout.addWidget(make_hairline())
        panel_layout.addLayout(editor)
        panel_layout.addWidget(self.todo_list, 1)
        panel_layout.addLayout(bottom)

        shell = QFrame()
        shell.setObjectName("dialogShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(title_bar("待办", self))
        content_wrap = transparent_frame()
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.addWidget(panel)
        shell_layout.addWidget(content_wrap, 1)
        self.resize_grip = add_resize_grip(shell_layout, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(shell)
        self.refresh_list()

    def activate_for_input(self) -> None:
        activate_input_window(self, self.todo_edit)

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
