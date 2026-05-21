"""Chat dialog and control-authorization cards."""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..constants.app import APP_NAME
from ..state.conversations import ChatHistoryMessage, ConversationSession, format_session_time
from .chat_components import ChatInputEdit, ChatMessageCard
from .dialog_chrome import (
    activate_input_window,
    add_resize_grip,
    enable_text_input,
    make_transparent,
    mark_button,
    setup_modern_dialog,
    styled_label,
    title_bar,
    transparent_frame,
    transparent_scroll_area,
)


class ChatDialog(QDialog):
    message_submitted = Signal(str, bool, str, bool)
    request_cancelled = Signal(str)
    control_plan_approved = Signal(str)
    control_plan_cancelled = Signal(str)
    session_selected = Signal(str)
    new_session_requested = Signal()
    history_clear_requested = Signal(str)
    memory_manage_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        context_hint: str = "",
        sessions: list[ConversationSession] | None = None,
        active_session: ConversationSession | None = None,
        history: list[ChatHistoryMessage] | None = None,
        use_conversation_context: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"问{APP_NAME}")
        setup_modern_dialog(self)
        self.resize(1120, 740)
        self.setMinimumSize(820, 540)
        self.context_removed = False
        self.context_check: QCheckBox | None = None
        self.context_chip: QFrame | None = None
        self.conversation_context_check = QCheckBox("使用模型上下文")
        self.conversation_context_check.setChecked(use_conversation_context)
        self.conversation_context_check.setToolTip(
            "只影响发送给模型的上下文，不影响本地会话历史。开启时会按设置携带会话上下文和长期记忆。"
        )
        self.waiting_for_reply = False
        self.session_rail_visible = False
        self.tool_rail_visible = False
        self.session_rail: QFrame | None = None
        self.tool_rail: QFrame | None = None
        self.active_session_id = active_session.session_id if active_session is not None else ""
        self.all_sessions: list[ConversationSession] = []
        self.message_widgets: list[QWidget] = []
        self.control_plan_buttons: dict[str, tuple[QPushButton, QPushButton, QLabel]] = {}

        self.session_list = QListWidget()
        self.session_list.setObjectName("sessionList")
        self.session_list.setMinimumWidth(188)
        self.session_list.setMaximumWidth(204)
        self.session_list.itemSelectionChanged.connect(self.emit_selected_session)

        self.session_search = QLineEdit()
        self.session_search.setObjectName("sessionSearch")
        self.session_search.setPlaceholderText("搜索会话")
        self.session_search.textChanged.connect(lambda _text="": self.render_sessions(self.active_session_id))

        new_button = QPushButton("新会话")
        mark_button(new_button, "primaryButton")
        new_button.clicked.connect(self.new_session_requested.emit)

        clear_button = QPushButton("清空当前")
        mark_button(clear_button, "quietButton")
        clear_button.clicked.connect(self.request_clear_history)

        memory_button = QPushButton("记忆")
        mark_button(memory_button, "secondaryButton")
        memory_button.setToolTip("查看、编辑或删除用户长期记忆。")
        memory_button.clicked.connect(self.memory_manage_requested.emit)

        self.history_content = make_transparent(QWidget())
        self.history_layout = QVBoxLayout(self.history_content)
        self.history_layout.setContentsMargins(8, 12, 8, 10)
        self.history_layout.setSpacing(14)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.history_scroll = transparent_scroll_area()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setWidget(self.history_content)

        self.text_edit = ChatInputEdit()
        self.text_edit.setObjectName("chatInput")
        self.text_edit.setPlaceholderText("告诉桌宠你的目标、卡点，或输入 / 命令调用工具")
        self.text_edit.setMinimumHeight(64)
        self.text_edit.setMaximumHeight(96)
        self.text_edit.submitted.connect(self.submit_message)
        enable_text_input(self.text_edit)
        enable_text_input(self.session_search)

        send_button = QPushButton("发送")
        mark_button(send_button, "primaryButton")
        send_button.clicked.connect(self.submit_message)
        self.send_button = send_button
        self.cancel_button = QPushButton("取消")
        mark_button(self.cancel_button, "secondaryButton")
        self.cancel_button.setToolTip("取消当前请求。")
        self.cancel_button.clicked.connect(self.cancel_current_request)
        self.cancel_button.hide()

        self.session_toggle_button = QPushButton("会话")
        mark_button(self.session_toggle_button, "railToggleButton")
        self.session_toggle_button.setToolTip("折叠或展开左侧会话栏")
        self.session_toggle_button.clicked.connect(self.toggle_session_rail)

        self.tool_toggle_button = QPushButton("工具")
        mark_button(self.tool_toggle_button, "railToggleButton")
        self.tool_toggle_button.setToolTip("折叠或展开右侧工具栏")
        self.tool_toggle_button.clicked.connect(self.toggle_tool_rail)

        panel = QFrame()
        panel.setObjectName("chatSurface")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        control_bar = QFrame()
        control_bar.setObjectName("chatControlBar")
        control_bar_layout = QHBoxLayout(control_bar)
        control_bar_layout.setContentsMargins(8, 4, 8, 2)
        control_bar_layout.setSpacing(8)
        control_bar_layout.addWidget(self.session_toggle_button, 0)
        control_bar_layout.addStretch(1)
        control_bar_layout.addWidget(self.tool_toggle_button, 0)
        panel_layout.addWidget(control_bar, 0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.session_rail = self._build_session_rail(new_button, clear_button, memory_button)
        body.addWidget(self.session_rail, 0)
        body.addWidget(self._build_conversation_center(context_hint, send_button), 1)
        self.tool_rail = self._build_tool_rail()
        body.addWidget(self.tool_rail, 0)
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
        shell_layout.addWidget(content_wrap, 1)
        self.resize_grip = add_resize_grip(shell_layout, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(shell)
        self.set_sessions(sessions or [], self.active_session_id)
        self.set_active_session(active_session, history or [])

    def _build_session_rail(self, new_button: QPushButton, clear_button: QPushButton, memory_button: QPushButton) -> QFrame:
        rail = QFrame()
        rail.setObjectName("chatSessionRail")
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(14, 14, 12, 14)
        rail_layout.setSpacing(10)
        rail_header = QHBoxLayout()
        rail_header.setContentsMargins(0, 0, 0, 0)
        rail_header.setSpacing(8)
        rail_header.addWidget(styled_label("会话", "railTitle"), 1)
        rail_header.addWidget(styled_label("local", "chatMeta"))
        rail_layout.addLayout(rail_header)
        rail_layout.addWidget(styled_label("当前 / 最近", "railSectionTitle"))
        rail_layout.addWidget(self.session_search)
        rail_layout.addWidget(self.session_list, 1)
        rail_buttons = QHBoxLayout()
        rail_buttons.setContentsMargins(0, 0, 0, 0)
        rail_buttons.setSpacing(8)
        rail_buttons.addWidget(new_button)
        rail_buttons.addWidget(clear_button)
        rail_layout.addLayout(rail_buttons)
        rail_layout.addWidget(memory_button)
        rail.setMaximumWidth(232)
        rail.setVisible(self.session_rail_visible)
        return rail

    def _build_conversation_center(self, context_hint: str, send_button: QPushButton) -> QFrame:
        center = QFrame()
        center.setObjectName("conversationCanvas")
        conversation = QVBoxLayout()
        center.setLayout(conversation)
        conversation.setContentsMargins(6, 4, 6, 8)
        conversation.setSpacing(10)

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
        composer_layout.setContentsMargins(12, 9, 12, 10)
        composer_layout.setSpacing(8)
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
            chip_close_button = QPushButton("×")
            mark_button(chip_close_button, "chipCloseButton")
            chip_close_button.clicked.connect(self.remove_drop_context)
            chip_layout.addWidget(chip_close_button)
            composer_layout.addWidget(self.context_chip)
        composer_layout.addWidget(self.text_edit)

        composer_buttons = QHBoxLayout()
        composer_buttons.setContentsMargins(0, 0, 0, 0)
        composer_buttons.setSpacing(8)
        composer_buttons.addWidget(self.conversation_context_check)
        composer_buttons.addStretch(1)
        composer_buttons.addWidget(self.cancel_button)
        composer_buttons.addWidget(send_button)
        composer_layout.addLayout(composer_buttons)
        conversation.addWidget(composer, 0)
        return center

    def _build_tool_rail(self) -> QFrame:
        tool_rail = QFrame()
        tool_rail.setObjectName("toolRail")
        tool_rail.setFixedWidth(202)
        tool_rail_layout = QVBoxLayout(tool_rail)
        tool_rail_layout.setContentsMargins(0, 0, 0, 0)
        tool_rail_layout.setSpacing(0)

        tool_content = make_transparent(QWidget())
        tool_layout = QVBoxLayout(tool_content)
        tool_layout.setContentsMargins(12, 14, 14, 14)
        tool_layout.setSpacing(12)
        tool_layout.addWidget(styled_label("工具", "railTitle"))
        tool_layout.addWidget(styled_label("常用命令会插入输入框；需要风险确认的动作会在会话里生成授权卡。", "mutedLabel", True))

        quick_group = QFrame()
        quick_group.setObjectName("toolGroup")
        quick_layout = QVBoxLayout(quick_group)
        quick_layout.setContentsMargins(10, 10, 10, 10)
        quick_layout.setSpacing(8)
        for label, template, tooltip in (
            ("系统状态", "/sys", "查看当前运行环境。"),
            ("当前目录", "/pwd", "查看默认工作目录。"),
            ("列出文件", "/ls ", "列出指定目录。"),
            ("读取文件", "/read ", "读取一个文件。"),
            ("搜索内容", "/search  ", "在路径中搜索关键词。"),
        ):
            quick_layout.addWidget(self.make_tool_button(label, template, tooltip))
        tool_layout.addWidget(quick_group)

        action_group = QFrame()
        action_group.setObjectName("toolGroup")
        action_layout = QVBoxLayout(action_group)
        action_layout.setContentsMargins(10, 10, 10, 10)
        action_layout.setSpacing(8)
        action_layout.addWidget(styled_label("授权动作", "sectionTitle"))
        for label, template, tooltip in (
            ("打开路径", "/open ", "打开文件、目录或 URL，需要确认。"),
            ("运行命令", "/run ", "运行外部命令，需要确认。"),
            ("写入文件", "/write  :: ", "写入文件内容，需要确认。"),
        ):
            action_layout.addWidget(self.make_tool_button(label, template, tooltip))
        tool_layout.addWidget(action_group)
        tool_layout.addWidget(styled_label("对话中直接描述目标也可以触发同一套授权流程。", "mutedLabel", True))
        tool_layout.addStretch(1)
        tool_scroll = transparent_scroll_area()
        tool_scroll.setWidgetResizable(True)
        tool_scroll.setWidget(tool_content)
        tool_rail_layout.addWidget(tool_scroll, 1)
        tool_rail.setVisible(self.tool_rail_visible)
        return tool_rail

    def text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def make_tool_button(self, label: str, template: str, tooltip: str) -> QPushButton:
        button = QPushButton(label)
        mark_button(button, "toolChipButton")
        button.setToolTip(tooltip)
        button.clicked.connect(lambda _checked=False, value=template: self.insert_command_template(value))
        return button

    def insert_command_template(self, template: str) -> None:
        existing = self.text_edit.toPlainText()
        separator = "\n" if existing and not existing.endswith("\n") else ""
        self.text_edit.setPlainText(f"{existing}{separator}{template}")
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def toggle_session_rail(self) -> None:
        self.session_rail_visible = not self.session_rail_visible
        if self.session_rail is not None:
            self.session_rail.setVisible(self.session_rail_visible)
        self.session_toggle_button.setText("隐藏会话" if self.session_rail_visible else "会话")

    def toggle_tool_rail(self) -> None:
        self.tool_rail_visible = not self.tool_rail_visible
        if self.tool_rail is not None:
            self.tool_rail.setVisible(self.tool_rail_visible)
        self.tool_toggle_button.setText("隐藏工具" if self.tool_rail_visible else "工具")

    def set_sessions(self, sessions: list[ConversationSession], active_session_id: str) -> None:
        self.all_sessions = list(sessions)
        self.render_sessions(active_session_id)

    def add_session_section(self, title: str) -> None:
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, "")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setPointSize(10)
        font.setBold(True)
        item.setFont(font)
        item.setForeground(QBrush(QColor("#8f8f8f")))
        self.session_list.addItem(item)

    def add_session_item(self, session: ConversationSession, active_session_id: str) -> None:
        title = session.title or "新会话"
        meta = f"{format_session_time(session.updated_at)} · {session.message_count} 条"
        item = QListWidgetItem(f"{title}\n{meta}")
        item.setData(Qt.ItemDataRole.UserRole, session.session_id)
        self.session_list.addItem(item)
        if session.session_id == active_session_id:
            self.session_list.setCurrentItem(item)

    def render_sessions(self, active_session_id: str) -> None:
        self.session_list.blockSignals(True)
        self.session_list.clear()
        query = self.session_search.text().strip().lower() if hasattr(self, "session_search") else ""
        visible_sessions: list[ConversationSession] = []
        for session in self.all_sessions:
            title = session.title or "新会话"
            meta = f"{format_session_time(session.updated_at)} · {session.message_count} 条"
            summary = " ".join(session.memory_items[-2:]) if session.memory_items else session.summary
            haystack = f"{title} {meta} {summary}".lower()
            if query and query not in haystack:
                continue
            visible_sessions.append(session)
        active_sessions = [session for session in visible_sessions if session.session_id == active_session_id]
        recent_sessions = [session for session in visible_sessions if session.session_id != active_session_id]
        if active_sessions:
            self.add_session_section("当前会话")
            for session in active_sessions:
                self.add_session_item(session, active_session_id)
        if recent_sessions:
            self.add_session_section("最近会话")
            for session in recent_sessions:
                self.add_session_item(session, active_session_id)
        if not visible_sessions:
            self.add_session_section("无匹配会话")
        self.session_list.blockSignals(False)

    def set_active_session(
        self,
        session: ConversationSession | None,
        messages: list[ChatHistoryMessage] | None = None,
    ) -> None:
        if session is not None:
            self.active_session_id = session.session_id
        else:
            self.active_session_id = ""
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
        empty = QFrame()
        empty.setObjectName("emptyState")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(18, 18, 18, 18)
        empty_layout.setSpacing(6)
        title = styled_label("开始对话", "sectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = styled_label("直接写目标或问题，需要工具时会在会话中请求授权。", "mutedLabel", True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title)
        empty_layout.addWidget(subtitle)
        empty_layout.addStretch(1)
        self.history_layout.addWidget(empty)
        self.message_widgets = [empty]

    def remove_empty_state(self) -> None:
        if len(self.message_widgets) != 1:
            return
        widget = self.message_widgets[0]
        if widget.objectName() == "emptyState":
            self.history_layout.removeWidget(widget)
            widget.deleteLater()
            self.message_widgets = []

    def assistant_avatar(self) -> QFrame:
        avatar = QFrame()
        avatar.setObjectName("assistantAvatar")
        avatar.setFixedSize(30, 30)
        layout = QVBoxLayout(avatar)
        layout.setContentsMargins(0, 0, 0, 0)
        label = styled_label("宠", "avatarText")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return avatar

    def add_message(self, role: str, content: str, ts: int | None = None) -> None:
        text = str(content or "").strip()
        if not text:
            return
        role = "assistant" if role == "assistant" else "user"
        self.remove_empty_state()

        row = make_transparent(QWidget())
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        card = ChatMessageCard(role, text)

        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(card, 0)
        else:
            row_layout.addWidget(self.assistant_avatar(), 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(card, 1)
            row_layout.addStretch(1)
        self.history_layout.addWidget(row)
        self.message_widgets.append(row)
        self.scroll_to_bottom()

    def add_user_message(self, content: str) -> None:
        self.add_message("user", content, int(time.time()))

    def add_assistant_message(self, content: str) -> None:
        self.add_message("assistant", content, int(time.time()))

    def add_control_plan(self, plan_id: str, title: str, details: str, requires_confirmation: bool) -> None:
        self.remove_empty_state()
        row = make_transparent(QWidget())
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("controlPlan")
        card.setMaximumWidth(660)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(9)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(styled_label("工具调用", "chatRole"))
        header.addStretch(1)
        header.addWidget(styled_label("等待授权" if requires_confirmation else "只读执行", "statusPill"))
        card_layout.addLayout(header)
        card_layout.addWidget(styled_label(title, "sectionTitle"))
        if requires_confirmation:
            card_layout.addWidget(styled_label("请确认目标和内容，授权前不会执行。", "chatMeta"))
        card_layout.addWidget(self.make_tool_detail_panel(details))
        status_label = styled_label("等待你的授权" if requires_confirmation else "准备执行", "chatMeta")
        card_layout.addWidget(status_label)

        if requires_confirmation:
            footer = QFrame()
            footer.setObjectName("permissionFooter")
            buttons = QHBoxLayout(footer)
            buttons.setContentsMargins(0, 0, 0, 0)
            buttons.setSpacing(8)
            run_button = QPushButton("允许本次")
            cancel_button = QPushButton("拒绝")
            mark_button(run_button, "primaryButton")
            mark_button(cancel_button, "secondaryButton")
            run_button.clicked.connect(lambda _checked=False, target=plan_id: self.approve_control_plan(target))
            cancel_button.clicked.connect(lambda _checked=False, target=plan_id: self.cancel_control_plan(target))
            buttons.addWidget(styled_label("需要授权", "chatMeta"))
            buttons.addStretch(1)
            buttons.addWidget(cancel_button)
            buttons.addWidget(run_button)
            card_layout.addWidget(footer)
            self.control_plan_buttons[plan_id] = (run_button, cancel_button, status_label)

        row_layout.addWidget(self.assistant_avatar(), 0, Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(card, 0)
        row_layout.addStretch(1)
        self.history_layout.addWidget(row)
        self.message_widgets.append(row)
        self.scroll_to_bottom()

    def make_tool_detail_panel(self, details: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("toolDetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(0)
        detail_label = styled_label(details, "toolDetailText", True)
        detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(detail_label)
        return panel

    def approve_control_plan(self, plan_id: str) -> None:
        self.set_control_plan_status(plan_id, "已授权，执行中", enabled=False)
        self.control_plan_approved.emit(plan_id)

    def cancel_control_plan(self, plan_id: str) -> None:
        self.set_control_plan_status(plan_id, "已取消，未执行", enabled=False)
        self.control_plan_cancelled.emit(plan_id)

    def set_control_plan_status(self, plan_id: str, status: str, *, enabled: bool) -> None:
        buttons = self.control_plan_buttons.get(plan_id)
        if buttons is None:
            return
        run_button, cancel_button, status_label = buttons
        run_button.setEnabled(enabled)
        cancel_button.setEnabled(enabled)
        status_label.setText(status)

    def scroll_to_bottom(self) -> None:
        QTimer.singleShot(0, lambda: self.history_scroll.verticalScrollBar().setValue(self.history_scroll.verticalScrollBar().maximum()))

    def set_waiting(self, waiting: bool) -> None:
        self.waiting_for_reply = waiting
        self.send_button.setEnabled(not waiting)
        self.send_button.setText("思考中" if waiting else "发送")
        self.cancel_button.setVisible(waiting)
        self.cancel_button.setEnabled(waiting)

    def submit_message(self) -> None:
        if self.waiting_for_reply:
            return
        user_text = self.text()
        if not user_text:
            return
        self.text_edit.clear()
        self.set_waiting(True)
        self.message_submitted.emit(
            user_text,
            self.use_drop_context(),
            self.active_session_id,
            self.use_conversation_context(),
        )

    def cancel_current_request(self) -> None:
        if not self.waiting_for_reply:
            return
        self.set_waiting(False)
        self.request_cancelled.emit(self.active_session_id)

    def request_clear_history(self) -> None:
        self.history_clear_requested.emit(self.active_session_id)

    def use_drop_context(self) -> bool:
        return self.context_check is not None and self.context_check.isChecked() and not self.context_removed

    def use_conversation_context(self) -> bool:
        return self.conversation_context_check.isChecked()

    def drop_context_was_removed(self) -> bool:
        return self.context_removed

    def remove_drop_context(self) -> None:
        self.context_removed = True
        if self.context_chip is not None:
            self.context_chip.hide()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        QTimer.singleShot(0, self.focus_composer)

    def focus_composer(self) -> None:
        activate_input_window(self, self.text_edit)

    def activate_for_input(self) -> None:
        activate_input_window(self, self.text_edit)
