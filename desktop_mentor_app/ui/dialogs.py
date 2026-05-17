"""Dialog widgets and shared QSS."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QDateTime, QPoint, QRect, QRectF, QTimer, Qt, QEvent, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..agent_client import compact_text
from ..assets import DEFAULT_IMAGE, TODO_BADGE_IMAGE
from ..config_store import AgentConfig, config_path
from ..conversation_store import ChatHistoryMessage, ConversationSession, format_session_time
from ..constants import (
    APP_NAME,
    DEFAULT_IDLE_MODE,
    DEFAULT_IDLE_SECONDS,
    DEFAULT_MODEL,
    DEFAULT_PERSONALITY_PROMPT,
    DEFAULT_CLICK_MESSAGE,
    DEFAULT_DROP_MESSAGE,
    DEFAULT_IDLE_MESSAGE,
    DEFAULT_MESSAGE_SECONDS,
    DEFAULT_MEMORY_TURNS,
    DEFAULT_TODO_REPEAT_SECONDS,
    IDLE_MODE_OPTIONS,
    MAX_IDLE_SECONDS,
    MAX_STICKER_FRAMES,
    MAX_MEMORY_TURNS,
    MAX_MESSAGE_SECONDS,
    MAX_TODO_REPEAT_SECONDS,
    MIN_IDLE_SECONDS,
    MIN_MESSAGE_SECONDS,
    MIN_TODO_REPEAT_SECONDS,
    STICKER_ACTION_LABELS,
    STICKER_ACTIONS,
    STICKER_IMAGE_FILTER,
)
from ..stickers import discover_sticker_sets, normalize_sticker_sets
from ..todo_store import format_due_time, load_todos_from_items
from .tokens import FULLSCREEN_ALERT_DURATION_MS


APP_STYLESHEET = """
* {
    font-family: "SF Pro Text", "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
}
QDialog {
    background: transparent;
    color: #dce6f3;
    font-size: 13px;
}
QWidget#dialogSurface {
    background: transparent;
}
QWidget#transparentSurface, QFrame#transparentSurface, QWidget#transparentViewport {
    background: transparent;
    border: 0;
}
QScrollArea#transparentScrollArea {
    background: transparent;
    border: 0;
}
QScrollArea#transparentScrollArea > QWidget, QScrollArea#transparentScrollArea QWidget#transparentViewport {
    background: transparent;
    border: 0;
}
QFrame#dialogShell {
    background: #101827;
    border: 1px solid #25364f;
    border-radius: 18px;
}
QFrame#titleBar {
    background: #101827;
    border-top-left-radius: 18px;
    border-top-right-radius: 18px;
    border-bottom: 1px solid #25364f;
}
QFrame#settingsRail {
    background: #0d1523;
    border: 1px solid #22324a;
    border-radius: 16px;
}
QFrame#sectionCard, QFrame#glassPanel {
    background: #111b2b;
    border: 1px solid #263852;
    border-radius: 14px;
}
QFrame#contextChip {
    background: #0d1726;
    border: 1px solid #2a4161;
    border-radius: 12px;
}
QFrame#chatTranscript {
    background: #0a111d;
    border: 1px solid #263852;
    border-radius: 14px;
}
QFrame#chatBubbleAssistant {
    background: #111b2b;
    border: 1px solid #2a4161;
    border-radius: 14px;
}
QFrame#chatBubbleUser {
    background: #1e4f7d;
    border: 1px solid #4a9ad6;
    border-radius: 14px;
}
QFrame#chatComposer {
    background: #0d1523;
    border: 1px solid #22324a;
    border-radius: 14px;
}
QFrame#sessionRail {
    background: #0d1523;
    border: 1px solid #22324a;
    border-radius: 14px;
}
QFrame#conversationHeader {
    background: #0d1726;
    border: 1px solid #25364f;
    border-radius: 14px;
}
QFrame#memoryStrip {
    background: #101827;
    border: 1px solid #2a4161;
    border-radius: 12px;
}
QFrame#hairline {
    background: #24364f;
    border: 0;
    min-height: 1px;
    max-height: 1px;
}
QFrame#settingsFooter {
    background: #0d1523;
    border-top: 1px solid #25364f;
    border-bottom-left-radius: 18px;
    border-bottom-right-radius: 18px;
}
QLabel {
    color: #d7dfec;
    background: transparent;
}
QLabel#dialogTitle {
    color: #edf4fb;
    font-size: 18px;
    font-weight: 700;
}
QLabel#windowCaption {
    color: #dce6f3;
    font-size: 13px;
    font-weight: 650;
}
QLabel#dialogSubtitle, QLabel#mutedLabel {
    color: #8da0b8;
}
QLabel#sectionTitle {
    color: #e8f0fa;
    font-size: 14px;
    font-weight: 650;
}
QLabel#railTitle {
    color: #dce6f3;
    font-size: 15px;
    font-weight: 700;
}
QLabel#chatRole {
    color: #8da0b8;
    font-size: 11px;
    font-weight: 650;
}
QLabel#chatText {
    color: #edf4fb;
    font-size: 13px;
    line-height: 1.35em;
}
QLabel#chatMeta {
    color: #72849b;
    font-size: 11px;
}
QLabel#sessionTitle {
    color: #edf4fb;
    font-size: 14px;
    font-weight: 700;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox, QListWidget {
    background: #0a111d;
    border: 1px solid #2a3c56;
    border-radius: 11px;
    color: #edf4fb;
    padding: 9px 11px;
    selection-background-color: #2f7fc7;
    selection-color: #ffffff;
}
QLineEdit:hover, QTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateTimeEdit:hover, QComboBox:hover, QListWidget:hover {
    border-color: #3e6f9e;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus, QListWidget:focus {
    border: 1px solid #4a9ad6;
    background: #0d1726;
}
QTextEdit {
    padding: 12px;
}
QCheckBox {
    color: #d7dfec;
    spacing: 9px;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 6px;
    border: 1px solid #344a68;
    background: #0a111d;
}
QCheckBox::indicator:hover {
    border-color: #4a9ad6;
}
QCheckBox::indicator:checked {
    background: #2f7fc7;
    border-color: #58a7de;
}
QPushButton {
    background: #142033;
    border: 1px solid #2b3f5b;
    border-radius: 11px;
    color: #edf4fb;
    padding: 9px 15px;
    min-height: 18px;
}
QPushButton:hover {
    background: #182842;
    border-color: #447eb2;
}
QPushButton:pressed {
    background: #1e5787;
}
QPushButton#primaryButton {
    background: #2f7fc7;
    border: 1px solid #58a7de;
    color: #ffffff;
    font-weight: 650;
}
QPushButton#primaryButton:hover {
    background: #368bd5;
}
QPushButton#secondaryButton {
    background: #111b2b;
}
QPushButton#quietButton {
    background: transparent;
    border: 1px solid #263852;
    color: #9db0c7;
}
QPushButton#quietButton:hover {
    background: #111b2b;
    border-color: #447eb2;
    color: #edf4fb;
}
QPushButton#miniButton {
    padding: 8px 12px;
    min-width: 58px;
}
QPushButton#railNavButton, QPushButton#railNavButtonActive {
    text-align: left;
    border-radius: 10px;
    padding: 9px 11px;
    min-height: 20px;
}
QPushButton#railNavButton {
    background: transparent;
    border: 1px solid transparent;
    color: #8fa3bb;
}
QPushButton#railNavButton:hover {
    background: #111b2b;
    border-color: #22324a;
    color: #dce6f3;
}
QPushButton#railNavButtonActive {
    background: #172842;
    border: 1px solid #31567d;
    color: #edf4fb;
}
QPushButton#chipCloseButton {
    background: #101827;
    border: 1px solid #2a4161;
    border-radius: 10px;
    color: #8da0b8;
    padding: 2px 8px;
    min-width: 22px;
    max-width: 26px;
    min-height: 22px;
    max-height: 26px;
}
QPushButton#chipCloseButton:hover {
    background: #172842;
    color: #edf4fb;
    border-color: #447eb2;
}
QPushButton#dangerButton {
    background: #3a1c26;
    border-color: #764153;
}
QPushButton#dangerButton:hover {
    background: #4d2431;
    border-color: #a35b70;
}
QPushButton#titleCloseButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    color: #8fa3bb;
    font-size: 15px;
    padding: 0;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#titleCloseButton:hover {
    background: #263852;
    border-color: #3e6f9e;
    color: #edf4fb;
}
QDialogButtonBox QPushButton {
    min-width: 78px;
}
QComboBox::drop-down, QDateTimeEdit::drop-down, QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: 0;
    width: 24px;
}
QScrollArea {
    background: transparent;
    border: 0;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 8px 2px 8px 2px;
}
QScrollBar::handle:vertical {
    background: #314560;
    border-radius: 5px;
    min-height: 34px;
}
QScrollBar::handle:vertical:hover {
    background: #447eb2;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QListWidget {
    outline: 0;
    padding: 6px;
}
QListWidget::item {
    border-radius: 10px;
    padding: 10px 12px;
    margin: 3px 0;
    color: #dce6f3;
}
QListWidget::item:hover {
    background: #172842;
}
QListWidget::item:selected {
    background: #1e4f7d;
    color: #ffffff;
}
QMenu {
    background-color: #101827;
    border: 1px solid #2a3c56;
    border-radius: 12px;
    color: #dce6f3;
    padding: 7px;
    margin: 0;
}
QMenu::item {
    background: transparent;
    border-radius: 10px;
    padding: 9px 34px 9px 14px;
}
QMenu::item:selected {
    background: #172842;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #24364f;
    margin: 7px 9px;
}
"""


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
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    dialog.setStyleSheet(APP_STYLESHEET)
    dialog.setObjectName("dialogSurface")


def prepare_modern_menu(menu: QMenu) -> QMenu:
    menu.setStyleSheet(APP_STYLESHEET)
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
        close_button = QPushButton("x")
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


class StickerSetEditor(QWidget):
    def __init__(self, sticker_sets: dict[str, list[str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        make_transparent(self)
        self.edits: dict[str, QTextEdit] = {}
        self.count_labels: dict[str, QLabel] = {}
        normalized = normalize_sticker_sets(sticker_sets)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        intro = QHBoxLayout()
        intro.setContentsMargins(0, 0, 0, 0)
        intro.setSpacing(8)
        intro.addWidget(styled_label("每行一张图片，按播放顺序排列；也可一次导入包含 8 个动作子目录的素材根目录。", "mutedLabel", True), 1)
        import_button = QPushButton("导入动作目录")
        mark_button(import_button, "miniButton")
        import_button.clicked.connect(self.browse_root_dir)
        intro.addWidget(import_button)
        layout.addLayout(intro)

        for action in STICKER_ACTIONS:
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(8)
            header.addWidget(styled_label(STICKER_ACTION_LABELS[action], "sectionTitle"), 1)
            count_label = styled_label("", "mutedLabel")
            self.count_labels[action] = count_label
            header.addWidget(count_label)

            select_button = QPushButton("按顺序选择")
            mark_button(select_button, "miniButton")
            select_button.clicked.connect(lambda _checked=False, target=action: self.browse_action(target))
            header.addWidget(select_button)

            clear_button = QPushButton("清空")
            mark_button(clear_button, "miniButton")
            clear_button.clicked.connect(lambda _checked=False, target=action: self.clear_action(target))
            header.addWidget(clear_button)

            edit = QTextEdit()
            edit.setAcceptRichText(False)
            edit.setMinimumHeight(58)
            edit.setMaximumHeight(86)
            edit.setPlaceholderText("每行一张图片路径；第一行是第 1 帧。")
            edit.setPlainText("\n".join(normalized.get(action, [])))
            edit.textChanged.connect(lambda target=action: self.update_count(target))
            self.edits[action] = edit

            layout.addLayout(header)
            layout.addWidget(edit)
            self.update_count(action)

    def action_paths(self, action: str) -> list[str]:
        edit = self.edits.get(action)
        if edit is None:
            return []
        return normalize_sticker_sets({action: edit.toPlainText()}).get(action, [])

    def browse_action(self, action: str) -> None:
        current_paths = self.action_paths(action)
        if current_paths:
            start_dir = str(Path(current_paths[0]).expanduser().parent)
        else:
            start_dir = str(Path.home())
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            f"选择 {STICKER_ACTION_LABELS[action]} 贴纸帧",
            start_dir,
            STICKER_IMAGE_FILTER,
        )
        if not paths:
            return
        self.edits[action].setPlainText("\n".join(paths[:MAX_STICKER_FRAMES]))
        self.update_count(action)

    def browse_root_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择动作贴纸根目录", str(Path.home()))
        if not path:
            return
        discovered = discover_sticker_sets(Path(path))
        for action, paths in discovered.items():
            edit = self.edits.get(action)
            if edit is not None:
                edit.setPlainText("\n".join(paths))
                self.update_count(action)

    def clear_action(self, action: str) -> None:
        edit = self.edits.get(action)
        if edit is None:
            return
        edit.clear()
        self.update_count(action)

    def update_count(self, action: str) -> None:
        label = self.count_labels.get(action)
        if label is None:
            return
        count = len(self.action_paths(action))
        label.setText(f"{count} frames")

    def to_sticker_sets(self) -> dict[str, list[str]]:
        return normalize_sticker_sets({action: self.action_paths(action) for action in STICKER_ACTIONS})


class SettingsDialog(QDialog):
    def __init__(self, config: AgentConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} 设置")
        setup_modern_dialog(self)
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        self.resize(min(920, max(720, available.width() - 120)), min(780, max(520, available.height() - 120)))
        self.setMinimumSize(680, 480)

        self.url_edit = QLineEdit(config.api_url)
        self.url_edit.setPlaceholderText("OpenAI-compatible base URL, e.g. http://127.0.0.1:8000")

        self.key_edit = QLineEdit(config.api_key)
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("API key")

        self.model_edit = QLineEdit(config.model or DEFAULT_MODEL)

        self.config_dir_edit = QLineEdit(config.config_dir or str(config_path().parent))
        self.config_dir_edit.setPlaceholderText("runtime config directory")
        config_dir_button = QPushButton("选择")
        mark_button(config_dir_button, "miniButton")
        config_dir_button.clicked.connect(self.browse_config_dir)
        config_dir_row = QHBoxLayout()
        config_dir_row.setContentsMargins(0, 0, 0, 0)
        config_dir_row.setSpacing(8)
        config_dir_row.addWidget(self.config_dir_edit, 1)
        config_dir_row.addWidget(config_dir_button)

        self.image_edit = QLineEdit(config.image_path or str(DEFAULT_IMAGE))
        self.image_edit.setPlaceholderText("PNG/JPG image path; PNG will be converted to ICO")
        image_button = QPushButton("选择")
        mark_button(image_button, "miniButton")
        image_button.clicked.connect(self.browse_image)
        image_row = QHBoxLayout()
        image_row.setContentsMargins(0, 0, 0, 0)
        image_row.setSpacing(8)
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

        self.todo_repeat_spin = QSpinBox()
        self.todo_repeat_spin.setRange(MIN_TODO_REPEAT_SECONDS, MAX_TODO_REPEAT_SECONDS)
        self.todo_repeat_spin.setSingleStep(30)
        self.todo_repeat_spin.setValue(max(MIN_TODO_REPEAT_SECONDS, min(MAX_TODO_REPEAT_SECONDS, int(config.todo_repeat_seconds or DEFAULT_TODO_REPEAT_SECONDS))))
        self.todo_repeat_spin.setSuffix(" s")

        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(MIN_IDLE_SECONDS, MAX_IDLE_SECONDS)
        self.idle_spin.setSingleStep(10)
        self.idle_spin.setValue(max(MIN_IDLE_SECONDS, min(MAX_IDLE_SECONDS, int(config.idle_seconds or DEFAULT_IDLE_SECONDS))))
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
        self.prompt_edit.setMinimumHeight(190)

        self.sticker_editor = StickerSetEditor(config.sticker_sets)

        agent_form = modern_form_layout()
        agent_form.addRow("Agent URL", self.url_edit)
        agent_form.addRow("API Key", self.key_edit)
        agent_form.addRow("Model", self.model_edit)

        runtime_form = modern_form_layout()
        runtime_form.addRow("Config directory", config_dir_row)
        runtime_form.addRow("Pet image", image_row)
        runtime_form.addRow("Message duration", self.message_seconds_spin)
        runtime_form.addRow("Todo repeat", self.todo_repeat_spin)

        interaction_form = modern_form_layout()
        interaction_form.addRow("Click message", self.click_message_edit)
        interaction_form.addRow("Idle message", self.idle_message_edit)
        interaction_form.addRow("Drop message", self.drop_message_edit)
        interaction_form.addRow("Idle reminder", self.idle_spin)
        interaction_form.addRow("Idle mode", self.idle_mode_combo)

        memory_form = modern_form_layout()
        memory_form.addRow("Memory", self.memory_check)
        memory_form.addRow("Memory depth", self.memory_turns_spin)

        sticker_layout = QVBoxLayout()
        sticker_layout.setContentsMargins(0, 0, 0, 0)
        sticker_layout.setSpacing(10)
        sticker_layout.addWidget(self.sticker_editor)

        prompt_layout = QVBoxLayout()
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(10)
        prompt_layout.addWidget(self.prompt_edit)

        self.section_cards: list[QFrame] = [
            section_card("Agent", agent_form),
            section_card("运行", runtime_form),
            section_card("互动", interaction_form),
            section_card("动作贴纸", sticker_layout, "这些素材只写入用户运行时配置，不复制进项目目录。"),
            section_card("记忆", memory_form),
            section_card("风格提示词", prompt_layout),
        ]
        self.nav_buttons: list[QPushButton] = []
        self.syncing_nav = False

        reset_prompt = QPushButton("恢复默认人格")
        mark_button(reset_prompt, "secondaryButton")
        reset_prompt.clicked.connect(lambda: self.prompt_edit.setPlainText(DEFAULT_PERSONALITY_PROMPT))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        style_dialog_buttons(buttons, QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(18, 12, 18, 12)
        bottom.setSpacing(10)
        bottom.addWidget(reset_prompt)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        rail = QFrame()
        rail.setObjectName("settingsRail")
        rail.setFixedWidth(168)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(14, 15, 14, 15)
        rail_layout.setSpacing(10)
        rail_layout.addWidget(styled_label(APP_NAME, "railTitle", True))
        rail_layout.addSpacing(6)
        for index, item_text in enumerate(("接口", "运行", "互动", "贴纸", "记忆", "风格")):
            nav = QPushButton(item_text)
            nav.setObjectName("railNavButtonActive" if index == 0 else "railNavButton")
            nav.setCursor(Qt.CursorShape.PointingHandCursor)
            nav.clicked.connect(lambda _checked=False, target=index: self.scroll_to_section(target))
            self.nav_buttons.append(nav)
            rail_layout.addWidget(nav)
        rail_layout.addStretch(1)
        rail_layout.addWidget(styled_label("runtime local", "mutedLabel"))

        subtitle = styled_label("接口、形象、提醒、记忆与话术集中配置。", "dialogSubtitle", True)

        content = make_transparent(QWidget())
        self.settings_content = content
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 12, 2)
        content_layout.setSpacing(14)
        content_layout.addWidget(subtitle)
        for card in self.section_cards:
            content_layout.addWidget(card)
        content_layout.addStretch(1)

        scroll = transparent_scroll_area()
        self.settings_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.verticalScrollBar().valueChanged.connect(self.sync_nav_to_scroll)

        main = QHBoxLayout()
        main.setContentsMargins(18, 18, 18, 12)
        main.setSpacing(16)
        main.addWidget(rail, 0)
        main.addWidget(scroll, 1)

        bottom_container = QFrame()
        bottom_container.setObjectName("settingsFooter")
        bottom_container.setLayout(bottom)

        shell = QFrame()
        shell.setObjectName("dialogShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(title_bar("设置", self))
        shell_layout.addLayout(main, 1)
        shell_layout.addWidget(bottom_container, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(shell)
        QTimer.singleShot(0, lambda: self.set_active_nav(0))

    def set_active_nav(self, active_index: int) -> None:
        for index, button in enumerate(self.nav_buttons):
            button.setObjectName("railNavButtonActive" if index == active_index else "railNavButton")
            restyle(button)

    def scroll_to_section(self, index: int) -> None:
        if index < 0 or index >= len(self.section_cards):
            return
        self.syncing_nav = True
        self.settings_scroll.ensureWidgetVisible(self.section_cards[index], 0, 14)
        self.set_active_nav(index)
        QTimer.singleShot(120, lambda: setattr(self, "syncing_nav", False))

    def sync_nav_to_scroll(self, _value: int) -> None:
        if self.syncing_nav:
            return
        viewport_top = self.settings_scroll.verticalScrollBar().value()
        active_index = 0
        for index, card in enumerate(self.section_cards):
            card_top = card.mapTo(self.settings_content, QPoint(0, 0)).y()
            if card_top <= viewport_top + 90:
                active_index = index
        self.set_active_nav(active_index)

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
            todo_repeat_seconds=int(self.todo_repeat_spin.value()),
            idle_seconds=int(self.idle_spin.value()),
            idle_mode=str(self.idle_mode_combo.currentData() or DEFAULT_IDLE_MODE),
            memory_enabled=self.memory_check.isChecked(),
            memory_turns=int(self.memory_turns_spin.value()),
            sticker_sets=self.sticker_editor.to_sticker_sets(),
            system_prompt=self.prompt_edit.toPlainText().strip() or DEFAULT_PERSONALITY_PROMPT,
        )


class ChatDialog(QDialog):
    message_submitted = Signal(str, bool, str)
    session_selected = Signal(str)
    new_session_requested = Signal()
    history_clear_requested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        context_hint: str = "",
        sessions: list[ConversationSession] | None = None,
        active_session: ConversationSession | None = None,
        history: list[ChatHistoryMessage] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"问{APP_NAME}")
        setup_modern_dialog(self)
        self.resize(840, 680)
        self.setMinimumSize(700, 480)
        self.context_removed = False
        self.context_check: QCheckBox | None = None
        self.context_chip: QFrame | None = None
        self.waiting_for_reply = False
        self.active_session_id = active_session.session_id if active_session is not None else ""
        self.message_widgets: list[QWidget] = []

        self.status_label = styled_label("就绪", "mutedLabel")
        self.session_title_label = styled_label("新会话", "dialogTitle")
        self.session_meta_label = styled_label("", "mutedLabel")
        self.memory_label = styled_label("暂无会话记忆", "mutedLabel", True)

        self.session_list = QListWidget()
        self.session_list.setMinimumWidth(210)
        self.session_list.setMaximumWidth(250)
        self.session_list.itemSelectionChanged.connect(self.emit_selected_session)

        new_button = QPushButton("新会话")
        mark_button(new_button, "primaryButton")
        new_button.clicked.connect(self.new_session_requested.emit)

        clear_button = QPushButton("清空当前")
        mark_button(clear_button, "quietButton")
        clear_button.clicked.connect(self.request_clear_history)

        self.history_content = make_transparent(QWidget())
        self.history_layout = QVBoxLayout(self.history_content)
        self.history_layout.setContentsMargins(12, 12, 12, 12)
        self.history_layout.setSpacing(10)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.history_scroll = transparent_scroll_area()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setWidget(self.history_content)

        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("chatInput")
        self.text_edit.setPlaceholderText("输入问题、目标或文件处理需求")
        self.text_edit.setMinimumHeight(82)
        self.text_edit.setMaximumHeight(118)

        send_button = QPushButton("发送")
        mark_button(send_button, "primaryButton")
        send_button.clicked.connect(self.submit_message)
        self.send_button = send_button

        dialog_close_button = QPushButton("关闭")
        mark_button(dialog_close_button, "secondaryButton")
        dialog_close_button.clicked.connect(self.reject)

        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 15, 16, 16)
        panel_layout.setSpacing(12)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        rail = QFrame()
        rail.setObjectName("sessionRail")
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(10, 10, 10, 10)
        rail_layout.setSpacing(10)
        rail_layout.addWidget(styled_label("会话", "railTitle"))
        rail_layout.addWidget(self.session_list, 1)
        rail_buttons = QHBoxLayout()
        rail_buttons.setContentsMargins(0, 0, 0, 0)
        rail_buttons.setSpacing(8)
        rail_buttons.addWidget(new_button)
        rail_buttons.addWidget(clear_button)
        rail_layout.addLayout(rail_buttons)
        body.addWidget(rail, 0)

        conversation = QVBoxLayout()
        conversation.setContentsMargins(0, 0, 0, 0)
        conversation.setSpacing(12)

        header = QFrame()
        header.setObjectName("conversationHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(5)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        title_box.addWidget(self.session_title_label)
        title_box.addWidget(self.session_meta_label)
        title_row.addLayout(title_box, 1)
        title_row.addWidget(self.status_label)
        header_layout.addLayout(title_row)
        memory_strip = QFrame()
        memory_strip.setObjectName("memoryStrip")
        memory_layout = QVBoxLayout(memory_strip)
        memory_layout.setContentsMargins(10, 7, 10, 7)
        memory_layout.addWidget(self.memory_label)
        header_layout.addWidget(memory_strip)
        conversation.addWidget(header, 0)

        transcript = QFrame()
        transcript.setObjectName("chatTranscript")
        transcript_layout = QVBoxLayout(transcript)
        transcript_layout.setContentsMargins(0, 0, 0, 0)
        transcript_layout.setSpacing(0)
        transcript_layout.addWidget(self.history_scroll)
        conversation.addWidget(transcript, 1)

        composer = QFrame()
        composer.setObjectName("chatComposer")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(12, 12, 12, 12)
        composer_layout.setSpacing(10)
        if context_hint:
            self.context_chip = QFrame()
            self.context_chip.setObjectName("contextChip")
            chip_layout = QHBoxLayout(self.context_chip)
            chip_layout.setContentsMargins(10, 8, 8, 8)
            chip_layout.setSpacing(8)
            self.context_check = QCheckBox("加载")
            self.context_check.setChecked(True)
            chip_layout.addWidget(self.context_check)
            chip_layout.addWidget(styled_label(context_hint, "mutedLabel", True), 1)
            chip_close_button = QPushButton("x")
            mark_button(chip_close_button, "chipCloseButton")
            chip_close_button.clicked.connect(self.remove_drop_context)
            chip_layout.addWidget(chip_close_button)
            composer_layout.addWidget(self.context_chip)
        composer_layout.addWidget(self.text_edit)

        composer_buttons = QHBoxLayout()
        composer_buttons.setContentsMargins(0, 0, 0, 0)
        composer_buttons.setSpacing(10)
        composer_buttons.addStretch(1)
        composer_buttons.addWidget(dialog_close_button)
        composer_buttons.addWidget(send_button)
        composer_layout.addLayout(composer_buttons)
        conversation.addWidget(composer, 0)

        body.addLayout(conversation, 1)
        panel_layout.addLayout(body, 1)

        shell = QFrame()
        shell.setObjectName("dialogShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(title_bar("对话", self))
        content_wrap = transparent_frame()
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.addWidget(panel)
        shell_layout.addWidget(content_wrap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(shell)
        self.set_sessions(sessions or [], self.active_session_id)
        self.set_active_session(active_session, history or [])

    def text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def set_sessions(self, sessions: list[ConversationSession], active_session_id: str) -> None:
        self.session_list.blockSignals(True)
        self.session_list.clear()
        for session in sessions:
            title = session.title or "新会话"
            meta = f"{format_session_time(session.updated_at)} · {session.message_count} 条"
            item = QListWidgetItem(f"{title}\n{meta}")
            item.setData(Qt.ItemDataRole.UserRole, session.session_id)
            self.session_list.addItem(item)
            if session.session_id == active_session_id:
                self.session_list.setCurrentItem(item)
        self.session_list.blockSignals(False)

    def set_active_session(
        self,
        session: ConversationSession | None,
        messages: list[ChatHistoryMessage] | None = None,
    ) -> None:
        if session is not None:
            self.active_session_id = session.session_id
            self.session_title_label.setText(session.title or "新会话")
            self.session_meta_label.setText(
                f"{format_session_time(session.updated_at)} · {session.message_count} 条消息"
            )
            if session.memory_items:
                preview = " · ".join(session.memory_items[-2:])
                self.memory_label.setText(f"记忆 {len(session.memory_items)} 条：{preview}")
            elif session.summary:
                self.memory_label.setText(f"摘要：{session.summary}")
            else:
                self.memory_label.setText("暂无会话记忆")
        else:
            self.active_session_id = ""
            self.session_title_label.setText("新会话")
            self.session_meta_label.setText("")
            self.memory_label.setText("暂无会话记忆")
        if messages is not None:
            self.set_history(messages)

    def emit_selected_session(self) -> None:
        items = self.session_list.selectedItems()
        if not items:
            return
        session_id = str(items[0].data(Qt.ItemDataRole.UserRole) or "")
        if session_id and session_id != self.active_session_id:
            self.session_selected.emit(session_id)

    def set_history(self, messages: list[ChatHistoryMessage]) -> None:
        self.clear_history_view()
        if not messages:
            self.add_empty_state()
            return
        for message in messages:
            self.add_message(message.role, message.content, message.ts)
        self.scroll_to_bottom()

    def clear_history_view(self) -> None:
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.message_widgets = []

    def add_empty_state(self) -> None:
        empty = styled_label("暂无会话", "mutedLabel")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setMinimumHeight(180)
        self.history_layout.addWidget(empty)
        self.message_widgets = [empty]

    def remove_empty_state(self) -> None:
        if len(self.message_widgets) != 1:
            return
        widget = self.message_widgets[0]
        if isinstance(widget, QLabel) and widget.text() == "暂无会话":
            self.history_layout.removeWidget(widget)
            widget.deleteLater()
            self.message_widgets = []

    def add_message(self, role: str, content: str, ts: int | None = None) -> None:
        text = str(content or "").strip()
        if not text:
            return
        role = "assistant" if role == "assistant" else "user"
        self.remove_empty_state()

        row = make_transparent(QWidget())
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        bubble = QFrame()
        bubble.setObjectName("chatBubbleUser" if role == "user" else "chatBubbleAssistant")
        bubble.setMaximumWidth(520)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 10)
        bubble_layout.setSpacing(5)

        role_label = styled_label("你" if role == "user" else APP_NAME, "chatRole")
        message_label = styled_label(text, "chatText", True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meta_label = styled_label(self.format_message_time(ts), "chatMeta")
        bubble_layout.addWidget(role_label)
        bubble_layout.addWidget(message_label)
        bubble_layout.addWidget(meta_label)

        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0)
        else:
            row_layout.addWidget(bubble, 0)
            row_layout.addStretch(1)
        self.history_layout.addWidget(row)
        self.message_widgets.append(row)
        self.scroll_to_bottom()

    def add_user_message(self, content: str) -> None:
        self.add_message("user", content, int(time.time()))

    def add_assistant_message(self, content: str) -> None:
        self.add_message("assistant", content, int(time.time()))

    @staticmethod
    def format_message_time(ts: int | None) -> str:
        if not ts:
            return ""
        try:
            return time.strftime("%H:%M", time.localtime(int(ts)))
        except Exception:
            return ""

    def scroll_to_bottom(self) -> None:
        QTimer.singleShot(0, lambda: self.history_scroll.verticalScrollBar().setValue(self.history_scroll.verticalScrollBar().maximum()))

    def set_waiting(self, waiting: bool) -> None:
        self.waiting_for_reply = waiting
        self.send_button.setEnabled(not waiting)
        self.status_label.setText("导师正在思考" if waiting else "就绪")

    def submit_message(self) -> None:
        if self.waiting_for_reply:
            return
        user_text = self.text()
        if not user_text:
            return
        self.text_edit.clear()
        self.add_user_message(user_text)
        self.set_waiting(True)
        self.message_submitted.emit(user_text, self.use_drop_context(), self.active_session_id)

    def request_clear_history(self) -> None:
        self.history_clear_requested.emit(self.active_session_id)

    def use_drop_context(self) -> bool:
        return self.context_check is not None and self.context_check.isChecked() and not self.context_removed

    def drop_context_was_removed(self) -> bool:
        return self.context_removed

    def remove_drop_context(self) -> None:
        self.context_removed = True
        if self.context_chip is not None:
            self.context_chip.hide()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.text_edit.setFocus(Qt.FocusReason.OtherFocusReason)


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
        shell_layout.addWidget(content_wrap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(shell)


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
        shell_layout.addWidget(content_wrap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(shell)
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
