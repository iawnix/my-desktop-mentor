"""Shared dialog chrome and styling helpers."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from .theme import apply_app_theme


def styled_label(text: str, object_name: str, word_wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(word_wrap)
    return label


def make_hairline() -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


def mark_button(button: QPushButton | None, object_name: str) -> None:
    if button is not None:
        button.setObjectName(object_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.style().unpolish(button)
        button.style().polish(button)


def restyle(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def make_transparent(widget: QWidget) -> QWidget:
    widget.setObjectName("transparentSurface")
    widget.setAutoFillBackground(False)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return widget


def enable_text_input(widget: QWidget) -> None:
    widget.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


def transparent_frame() -> QFrame:
    return make_transparent(QFrame())  # type: ignore[return-value]


def transparent_scroll_area() -> QScrollArea:
    scroll = QScrollArea()
    scroll.setObjectName("transparentScrollArea")
    scroll.setAutoFillBackground(False)
    scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    scroll.viewport().setObjectName("transparentViewport")
    scroll.viewport().setAutoFillBackground(False)
    scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return scroll


def style_dialog_buttons(buttons: QDialogButtonBox, primary: QDialogButtonBox.StandardButton | None = None) -> None:
    for button in buttons.buttons():
        mark_button(button, "secondaryButton")
    if primary is not None:
        mark_button(buttons.button(primary), "primaryButton")


def setup_modern_dialog(dialog: QDialog) -> None:
    dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    dialog.setWindowFlag(Qt.WindowType.Tool, False)
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    dialog.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
    apply_app_theme(dialog)
    dialog.setObjectName("dialogSurface")


def activate_input_window(dialog: QDialog, focus_widget: QWidget | None = None) -> None:
    """Activate a standalone text-capable dialog and refresh its input focus."""
    dialog.raise_()
    dialog.activateWindow()

    if focus_widget is None:
        return

    def focus_now() -> None:
        if not dialog.isVisible():
            return
        focus_widget.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        try:
            focus_widget.updateMicroFocus()
        except Exception:
            pass

    QTimer.singleShot(0, focus_now)
    QTimer.singleShot(80, focus_now)


def add_resize_grip(shell_layout: QVBoxLayout, owner: QDialog) -> QSizeGrip:
    row = make_transparent(QWidget(owner))
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 10, 8)
    row_layout.setSpacing(0)
    row_layout.addStretch(1)
    grip = QSizeGrip(row)
    grip.setObjectName("resizeGrip")
    grip.setToolTip("拖动调整窗口大小")
    grip.setCursor(Qt.CursorShape.SizeFDiagCursor)
    grip.setFixedSize(22, 22)
    row_layout.addWidget(grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
    shell_layout.addWidget(row, 0)
    return grip


def prepare_modern_menu(menu: QMenu) -> QMenu:
    apply_app_theme(menu)
    menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    menu.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
    return menu


class DialogTitleBar(QFrame):
    def __init__(self, title: str, owner: QDialog) -> None:
        super().__init__(owner)
        self.owner = owner
        self.drag_offset = QPoint()
        self.setObjectName("titleBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 9, 12, 9)
        layout.setSpacing(8)
        caption = styled_label(title, "windowCaption")
        layout.addWidget(caption)
        layout.addStretch(1)
        close_button = QPushButton("×")
        mark_button(close_button, "titleCloseButton")
        close_button.clicked.connect(owner.reject)
        layout.addWidget(close_button)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.owner.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.owner.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)


def title_bar(title: str, owner: QDialog) -> QFrame:
    return DialogTitleBar(title, owner)


def section_card(title: str, content_layout: QFormLayout | QVBoxLayout, subtitle: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("sectionCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 15, 16, 16)
    layout.setSpacing(10)
    layout.addWidget(styled_label(title, "sectionTitle"))
    if subtitle:
        layout.addWidget(styled_label(subtitle, "mutedLabel", True))
    layout.addWidget(make_hairline())
    layout.addLayout(content_layout)
    return frame


def modern_form_layout() -> QFormLayout:
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(12)
    return form
