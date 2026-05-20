"""Read-only text display dialog."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QTextEdit, QVBoxLayout, QWidget

from .dialog_chrome import (
    activate_input_window,
    add_resize_grip,
    setup_modern_dialog,
    style_dialog_buttons,
    styled_label,
    title_bar,
    transparent_frame,
)


class TextViewDialog(QDialog):
    def __init__(self, title: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        setup_modern_dialog(self)
        self.resize(620, 520)
        self.setMinimumSize(460, 360)

        text_view = QTextEdit()
        text_view.setReadOnly(True)
        text_view.setPlainText(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        style_dialog_buttons(buttons)
        buttons.rejected.connect(self.reject)

        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 15, 16, 16)
        panel_layout.setSpacing(12)
        panel_layout.addWidget(styled_label(title, "dialogTitle"))
        panel_layout.addWidget(text_view, 1)
        panel_layout.addWidget(buttons, 0)

        shell = QFrame()
        shell.setObjectName("dialogShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(title_bar(title, self))
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

    def activate_for_input(self) -> None:
        activate_input_window(self)
