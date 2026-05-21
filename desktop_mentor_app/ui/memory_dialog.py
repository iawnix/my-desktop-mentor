"""Long-term user memory editor."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..state.user_memory import (
    UserMemory,
    add_user_memory,
    delete_user_memory,
    load_user_memories,
    update_user_memory,
)
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


def format_memory_time(timestamp: int) -> str:
    from time import localtime, strftime

    try:
        return strftime("%Y-%m-%d %H:%M", localtime(int(timestamp)))
    except Exception:
        return ""


class UserMemoryDialog(QDialog):
    memories_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("长期记忆")
        setup_modern_dialog(self)
        self.resize(780, 560)
        self.setMinimumSize(620, 420)
        self.memories: list[UserMemory] = []
        self.active_memory_id = ""

        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        header.addWidget(styled_label("长期记忆", "dialogTitle"))
        header.addWidget(styled_label("本机用户级记忆，可逐条启用、编辑或删除。", "dialogSubtitle", True))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索长期记忆")
        self.search_edit.textChanged.connect(lambda _text="": self.refresh_list())
        enable_text_input(self.search_edit)

        self.memory_list = QListWidget()
        self.memory_list.setMinimumWidth(260)
        self.memory_list.itemSelectionChanged.connect(self.load_selected_memory)

        self.enabled_check = QCheckBox("启用")
        self.enabled_check.setChecked(True)
        self.memory_edit = QTextEdit()
        self.memory_edit.setPlaceholderText("写入一条长期记忆")
        self.memory_edit.setMinimumHeight(210)
        enable_text_input(self.memory_edit)

        self.detail_label = styled_label("未选择", "chatMeta", True)

        new_button = QPushButton("新建")
        mark_button(new_button, "secondaryButton")
        new_button.clicked.connect(self.start_new_memory)

        save_button = QPushButton("保存")
        mark_button(save_button, "primaryButton")
        save_button.clicked.connect(self.save_current_memory)

        delete_button = QPushButton("删除选中")
        mark_button(delete_button, "dangerButton")
        delete_button.clicked.connect(self.delete_selected_memory)

        edit_buttons = QHBoxLayout()
        edit_buttons.setContentsMargins(0, 0, 0, 0)
        edit_buttons.setSpacing(8)
        edit_buttons.addWidget(new_button)
        edit_buttons.addStretch(1)
        edit_buttons.addWidget(delete_button)
        edit_buttons.addWidget(save_button)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)
        left.addWidget(self.search_edit)
        left.addWidget(self.memory_list, 1)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)
        right.addWidget(self.enabled_check)
        right.addWidget(self.memory_edit, 1)
        right.addWidget(self.detail_label)
        right.addLayout(edit_buttons)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(14)
        columns.addLayout(left, 0)
        columns.addLayout(right, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        style_dialog_buttons(buttons)
        buttons.rejected.connect(self.reject)

        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 15, 16, 16)
        panel_layout.setSpacing(13)
        panel_layout.addLayout(header)
        panel_layout.addWidget(make_hairline())
        panel_layout.addLayout(columns, 1)
        panel_layout.addWidget(buttons, 0)

        shell = QFrame()
        shell.setObjectName("dialogShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(title_bar("长期记忆", self))
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
        activate_input_window(self, self.search_edit)

    def selected_memory_id(self) -> str:
        selected = self.memory_list.selectedItems()
        if not selected:
            return ""
        return str(selected[0].data(Qt.ItemDataRole.UserRole) or "")

    def memory_by_id(self, memory_id: str) -> UserMemory | None:
        for memory in self.memories:
            if memory.memory_id == memory_id:
                return memory
        return None

    def refresh_list(self, select_id: str = "") -> None:
        self.memories = load_user_memories()
        query = self.search_edit.text().strip().casefold()
        target_id = select_id or self.active_memory_id
        self.memory_list.blockSignals(True)
        self.memory_list.clear()
        selected_item: QListWidgetItem | None = None
        for memory in self.memories:
            haystack = f"{memory.text} {memory.source} {memory.session_id}".casefold()
            if query and query not in haystack:
                continue
            status = "启用" if memory.enabled else "停用"
            item = QListWidgetItem(f"{status}  {memory.text}\n{format_memory_time(memory.updated_at)} · {memory.source}")
            item.setData(Qt.ItemDataRole.UserRole, memory.memory_id)
            self.memory_list.addItem(item)
            if memory.memory_id == target_id:
                selected_item = item
        self.memory_list.blockSignals(False)
        if selected_item is not None:
            self.memory_list.setCurrentItem(selected_item)
            self.load_selected_memory()
        elif not target_id:
            self.start_new_memory(clear_selection=False)

    def load_selected_memory(self) -> None:
        memory = self.memory_by_id(self.selected_memory_id())
        if memory is None:
            return
        self.active_memory_id = memory.memory_id
        self.memory_edit.setPlainText(memory.text)
        self.enabled_check.setChecked(memory.enabled)
        created = format_memory_time(memory.created_at)
        updated = format_memory_time(memory.updated_at)
        self.detail_label.setText(f"来源 {memory.source} · 创建 {created} · 更新 {updated}")

    def start_new_memory(self, *, clear_selection: bool = True) -> None:
        self.active_memory_id = ""
        if clear_selection:
            self.memory_list.clearSelection()
        self.memory_edit.clear()
        self.enabled_check.setChecked(True)
        self.detail_label.setText("新长期记忆")
        self.memory_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def save_current_memory(self) -> None:
        text = self.memory_edit.toPlainText().strip()
        if not text:
            return
        if self.active_memory_id:
            memory = update_user_memory(self.active_memory_id, text=text, enabled=self.enabled_check.isChecked())
        else:
            memory = add_user_memory(text, source="manual", enabled=self.enabled_check.isChecked())
        if memory is None:
            return
        self.active_memory_id = memory.memory_id
        self.refresh_list(memory.memory_id)
        self.memories_changed.emit()

    def delete_selected_memory(self) -> None:
        memory_id = self.selected_memory_id() or self.active_memory_id
        if not memory_id:
            return
        if delete_user_memory(memory_id):
            self.active_memory_id = ""
            self.refresh_list()
            self.start_new_memory()
            self.memories_changed.emit()
