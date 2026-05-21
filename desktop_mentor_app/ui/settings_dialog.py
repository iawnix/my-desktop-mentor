"""Settings dialog for runtime configuration."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config.store import AgentConfig, config_path
from ..core.assets import DEFAULT_IMAGE
from ..constants import (
    APP_NAME,
    DEFAULT_CLICK_MESSAGE,
    DEFAULT_CONTROL_ENABLED,
    DEFAULT_CONTROL_WORKSPACE,
    DEFAULT_DROP_MESSAGE,
    DEFAULT_IDLE_MESSAGE,
    DEFAULT_IDLE_MODE,
    DEFAULT_IDLE_SECONDS,
    DEFAULT_MEMORY_TURNS,
    DEFAULT_MESSAGE_SECONDS,
    DEFAULT_MODEL,
    DEFAULT_PERSONALITY_PROMPT,
    DEFAULT_STICKER_ANIMATION_SPEED,
    DEFAULT_TODO_REPEAT_SECONDS,
    IDLE_MODE_OPTIONS,
    MAX_IDLE_SECONDS,
    MAX_MEMORY_TURNS,
    MAX_MESSAGE_SECONDS,
    MAX_STICKER_ANIMATION_SPEED,
    MAX_TODO_REPEAT_SECONDS,
    MIN_IDLE_SECONDS,
    MIN_MESSAGE_SECONDS,
    MIN_STICKER_ANIMATION_SPEED,
    MIN_TODO_REPEAT_SECONDS,
)
from .dialog_chrome import (
    activate_input_window,
    add_resize_grip,
    enable_text_input,
    make_transparent,
    mark_button,
    modern_form_layout,
    restyle,
    section_card,
    setup_modern_dialog,
    style_dialog_buttons,
    styled_label,
    title_bar,
    transparent_scroll_area,
)
from .sticker_set_editor import StickerSetEditor


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

        self.sticker_animation_speed_spin = QDoubleSpinBox()
        self.sticker_animation_speed_spin.setRange(MIN_STICKER_ANIMATION_SPEED, MAX_STICKER_ANIMATION_SPEED)
        self.sticker_animation_speed_spin.setSingleStep(0.25)
        self.sticker_animation_speed_spin.setDecimals(2)
        self.sticker_animation_speed_spin.setValue(
            max(
                MIN_STICKER_ANIMATION_SPEED,
                min(
                    MAX_STICKER_ANIMATION_SPEED,
                    float(config.sticker_animation_speed or DEFAULT_STICKER_ANIMATION_SPEED),
                ),
            )
        )
        self.sticker_animation_speed_spin.setSuffix(" x")

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

        self.memory_check = QCheckBox("默认携带当前会话上下文")
        self.memory_check.setChecked(bool(config.memory_enabled))

        self.memory_turns_spin = QSpinBox()
        self.memory_turns_spin.setRange(1, MAX_MEMORY_TURNS)
        self.memory_turns_spin.setValue(max(1, min(MAX_MEMORY_TURNS, int(config.memory_turns or DEFAULT_MEMORY_TURNS))))
        self.memory_turns_spin.setSuffix(" turns")

        self.control_check = QCheckBox("允许受控电脑操作")
        self.control_check.setChecked(bool(config.control_enabled if config.control_enabled is not None else DEFAULT_CONTROL_ENABLED))

        self.control_workspace_edit = QLineEdit(config.control_workspace or DEFAULT_CONTROL_WORKSPACE or str(Path.home()))
        self.control_workspace_edit.setPlaceholderText("默认电脑操作工作目录")
        control_workspace_button = QPushButton("选择")
        mark_button(control_workspace_button, "miniButton")
        control_workspace_button.clicked.connect(self.browse_control_workspace)
        control_workspace_row = QHBoxLayout()
        control_workspace_row.setContentsMargins(0, 0, 0, 0)
        control_workspace_row.setSpacing(8)
        control_workspace_row.addWidget(self.control_workspace_edit, 1)
        control_workspace_row.addWidget(control_workspace_button)

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
        memory_form.addRow("模型上下文", self.memory_check)
        memory_form.addRow("上下文轮数", self.memory_turns_spin)

        control_form = modern_form_layout()
        control_form.addRow("Computer control", self.control_check)
        control_form.addRow("Workspace", control_workspace_row)

        sticker_layout = QVBoxLayout()
        sticker_layout.setContentsMargins(0, 0, 0, 0)
        sticker_layout.setSpacing(10)
        sticker_form = modern_form_layout()
        sticker_form.addRow("Animation speed", self.sticker_animation_speed_spin)
        sticker_layout.addLayout(sticker_form)
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
            section_card("上下文", memory_form),
            section_card("电脑控制", control_form, "读操作直接执行；运行、打开和写入会先请求确认。"),
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
        for index, item_text in enumerate(("接口", "运行", "互动", "贴纸", "上下文", "电脑", "风格")):
            nav = QPushButton(item_text)
            nav.setObjectName("railNavButtonActive" if index == 0 else "railNavButton")
            nav.setCursor(Qt.CursorShape.PointingHandCursor)
            nav.clicked.connect(lambda _checked=False, target=index: self.scroll_to_section(target))
            self.nav_buttons.append(nav)
            rail_layout.addWidget(nav)
        rail_layout.addStretch(1)
        rail_layout.addWidget(styled_label("runtime local", "mutedLabel"))

        subtitle = styled_label("接口、形象、提醒、模型上下文与话术集中配置。", "dialogSubtitle", True)

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
        self.resize_grip = add_resize_grip(shell_layout, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(shell)
        for widget_type in (QLineEdit, QTextEdit):
            for widget in self.findChildren(widget_type):
                enable_text_input(widget)
        QTimer.singleShot(0, lambda: self.set_active_nav(0))

    def activate_for_input(self) -> None:
        activate_input_window(self)

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

    def browse_control_workspace(self) -> None:
        current = self.control_workspace_edit.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "选择电脑操作工作目录", str(Path(current).expanduser()))
        if path:
            self.control_workspace_edit.setText(path)

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
            control_enabled=self.control_check.isChecked(),
            control_workspace=self.control_workspace_edit.text().strip(),
            sticker_animation_speed=float(self.sticker_animation_speed_spin.value()),
            sticker_sets=self.sticker_editor.to_sticker_sets(),
            system_prompt=self.prompt_edit.toPlainText().strip() or DEFAULT_PERSONALITY_PROMPT,
        )
