"""Dialog and chat/control coordination for the desktop pet widget."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog

from ..config.store import save_config, save_config_directory
from ..constants.pet import IDLE_MODE_FULLSCREEN
from ..constants.stickers import STICKER_ACTION_ERROR, STICKER_ACTION_TAP, STICKER_ACTION_THINKING
from ..tools.drop_context import compose_prompt_with_drop_context
from ..state.conversations import (
    create_conversation_session,
    delete_conversation_session,
    ensure_active_session,
    get_session,
    list_conversation_sessions,
    load_chat_history,
    set_active_session,
)
from ..state.todos import load_todos, save_todos
from ..tools.registry import build_control_plan
from ..tools.types import ControlPlan
from .chat_dialog import ChatDialog
from .memory_dialog import UserMemoryDialog
from .settings_dialog import SettingsDialog
from .text_view_dialog import TextViewDialog
from .todo_dialog import TodoDialog


class PetDialogCoordinator:
    def __init__(self, pet: Any) -> None:
        self.pet = pet
        self.active_agent_tasks: dict[str, asyncio.Task[None]] = {}
        self.active_agent_prompts: dict[str, str] = {}
        self.memory_dialog: UserMemoryDialog | None = None

    def context_default_enabled(self) -> bool:
        config = self.pet.config
        return bool(getattr(config, "memory_enabled", False) or getattr(config, "long_term_memory_enabled", False))

    def open_settings(self) -> None:
        pet = self.pet
        pet.mark_interaction()
        dialog = SettingsDialog(pet.config)
        self.position_dialog_near_pet(dialog)
        dialog.activate_for_input()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        old_config = pet.config
        old_config_path = pet.config_path
        old_image_path = pet.image_path
        old_pixmap = pet.pixmap
        new_config = dialog.to_config()
        requested_config_dir = Path(new_config.config_dir or str(pet.config_path.parent)).expanduser()
        try:
            resolved_config_dir = requested_config_dir.resolve()
            resolved_config_dir.mkdir(parents=True, exist_ok=True)
            new_config.config_dir = str(resolved_config_dir)
            pet.config_path = resolved_config_dir / "config.json"
        except OSError as exc:
            pet.show_bubble(f"配置目录不可用：{type(exc).__name__}", duration=pet.message_duration(), action=STICKER_ACTION_ERROR)
            return
        pet.config = new_config
        if not pet.apply_image_from_config(old_image_path):
            pet.config = old_config
            pet.config_path = old_config_path
            pet.image_path = old_image_path
            pet.pixmap = old_pixmap
            pet.show_bubble("形象文件加载失败，设置未保存。", duration=pet.message_duration(), action=STICKER_ACTION_ERROR)
            return
        invalid_stickers = pet.reload_sticker_sets()
        icon_error = pet.refresh_window_icon()
        saved_dir = save_config_directory(resolved_config_dir)
        pet.config.config_dir = str(saved_dir)
        pet.config_path = saved_dir / "config.json"
        path = save_config(pet.config, pet.config_path)
        if pet.config_path != old_config_path:
            pet.todo_bubbles = []
            pet.recalculate_todo_stack_layout()
        if pet.config.idle_mode != IDLE_MODE_FULLSCREEN and pet.fullscreen_alert is not None:
            pet.fullscreen_alert.close()
        if icon_error:
            pet.show_bubble(f"设置已保存，但 ICO 生成失败：{icon_error}", duration=pet.message_duration(), action=STICKER_ACTION_ERROR)
        elif invalid_stickers:
            pet.show_bubble(f"设置已保存，但 {len(invalid_stickers)} 张动作贴纸加载失败。", duration=pet.message_duration(), action=STICKER_ACTION_ERROR)
        else:
            pet.show_bubble(f"设置已保存：{path}", duration=pet.message_duration())

    def open_todos(self) -> None:
        pet = self.pet
        pet.mark_interaction()
        dialog = TodoDialog(load_todos())
        self.position_dialog_near_pet(dialog)
        dialog.activate_for_input()
        dialog.exec()
        path = save_todos(dialog.todos)
        pet.sync_todo_bubbles_with_store()
        pet.show_bubble(f"待办已保存：{path}", duration=pet.message_duration())

    def drop_context_hint(self) -> str:
        pet = self.pet
        if not pet.last_drop_context:
            return ""
        count = len(pet.last_drop_paths)
        names = [Path(path).name or str(path) for path in pet.last_drop_paths[:3]]
        suffix = f"：{'、'.join(names)}" if names else ""
        if count > 3:
            suffix += f" 等 {count} 项"
        return f"文件上下文{suffix}"

    def open_chat(self) -> None:
        pet = self.pet
        pet.mark_interaction()
        if pet.chat_dialog is not None and pet.chat_dialog.isVisible():
            pet.chat_dialog.raise_()
            pet.chat_dialog.activateWindow()
            return

        active_session = ensure_active_session()
        dialog = ChatDialog(
            None,
            self.drop_context_hint(),
            list_conversation_sessions(),
            active_session,
            load_chat_history(active_session.session_id),
            use_conversation_context=self.context_default_enabled(),
        )
        dialog.message_submitted.connect(self.handle_chat_message)
        dialog.request_cancelled.connect(self.cancel_agent_request)
        dialog.control_plan_approved.connect(self.approve_control_plan)
        dialog.control_plan_cancelled.connect(self.cancel_control_plan)
        dialog.session_selected.connect(self.load_chat_session_in_dialog)
        dialog.new_session_requested.connect(self.create_chat_session_from_dialog)
        dialog.history_clear_requested.connect(self.clear_chat_history_from_dialog)
        dialog.memory_manage_requested.connect(self.open_memory_manager)
        dialog.finished.connect(lambda _code=0, target=dialog: self.clear_chat_dialog(target))
        pet.chat_dialog = dialog
        self.position_dialog_near_pet(dialog)
        dialog.show()
        dialog.activate_for_input()

    def clear_chat_dialog(self, dialog: ChatDialog) -> None:
        if self.pet.chat_dialog is dialog:
            self.pet.chat_dialog = None

    def refresh_chat_dialog_sessions(self) -> None:
        pet = self.pet
        if pet.chat_dialog is None:
            return
        active_id = pet.chat_dialog.active_session_id or ensure_active_session().session_id
        session = get_session(active_id) or ensure_active_session()
        pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
        pet.chat_dialog.set_active_session(session)

    def load_chat_session_in_dialog(self, session_id: str) -> None:
        pet = self.pet
        session = get_session(session_id)
        if session is None or pet.chat_dialog is None:
            return
        set_active_session(session.session_id)
        pet.chat_dialog.set_active_session(session, load_chat_history(session.session_id))

    def create_chat_session_from_dialog(self) -> None:
        pet = self.pet
        session = create_conversation_session()
        if pet.chat_dialog is not None:
            pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
            pet.chat_dialog.set_active_session(session, [])

    def clear_chat_history_from_dialog(self, session_id: str) -> None:
        pet = self.pet
        target_id = session_id or (pet.chat_dialog.active_session_id if pet.chat_dialog is not None else "")
        self.cancel_session_activity(target_id)
        session = delete_conversation_session(target_id)
        if pet.chat_dialog is not None:
            pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
            pet.chat_dialog.set_active_session(session, load_chat_history(session.session_id))
        pet.show_bubble("当前会话已删除。", duration=pet.message_duration(), action=STICKER_ACTION_TAP)

    def cancel_session_activity(self, session_id: str) -> None:
        if not session_id:
            return
        task = self.active_agent_tasks.pop(session_id, None)
        self.active_agent_prompts.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()
        for plan_id, pending in list(self.pet.pending_control_plans.items()):
            if len(pending) >= 3 and pending[2] == session_id:
                self.pet.pending_control_plans.pop(plan_id, None)
                self.pet.chat_service.discard_pending_agent_state(plan_id)

    def open_memory_manager(self) -> None:
        pet = self.pet
        pet.mark_interaction()
        pet.show_bubble("打开长期记忆。", duration=min(1.8, pet.message_duration()), action=STICKER_ACTION_TAP)
        if self.memory_dialog is not None and self.memory_dialog.isVisible():
            self.memory_dialog.raise_()
            self.memory_dialog.activate_for_input()
            return

        parent = pet.chat_dialog if pet.chat_dialog is not None and pet.chat_dialog.isVisible() else pet
        dialog = UserMemoryDialog(parent)
        dialog.setModal(False)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.memory_dialog = dialog
        changed = {"value": False}
        dialog.memories_changed.connect(lambda: changed.__setitem__("value", True))
        dialog.finished.connect(lambda _code=0, target=dialog: self.clear_memory_dialog(target, changed["value"]))
        if isinstance(parent, QDialog):
            self.position_dialog_near_dialog(dialog, parent)
        else:
            self.position_dialog_near_pet(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activate_for_input()
        QTimer.singleShot(0, dialog.activate_for_input)

    def clear_memory_dialog(self, dialog: UserMemoryDialog, changed: bool) -> None:
        if self.memory_dialog is dialog:
            self.memory_dialog = None
        dialog.deleteLater()
        if changed:
            self.pet.show_bubble("长期记忆已更新。", duration=self.pet.message_duration(), action=STICKER_ACTION_TAP)

    def session_for_context_policy(
        self,
        user_prompt: str,
        session_id: str,
        use_conversation_context: bool,
    ):
        return self.pet.chat_service.session_for_context_policy(user_prompt, session_id, use_conversation_context)

    def show_user_message_for_session(self, user_prompt: str, session_id: str) -> None:
        pet = self.pet
        if pet.chat_dialog is None:
            return
        session = get_session(session_id) or ensure_active_session()
        if pet.chat_dialog.active_session_id != session.session_id:
            pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
            pet.chat_dialog.set_active_session(session, load_chat_history(session.session_id))
        else:
            pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
        pet.chat_dialog.add_user_message(user_prompt)
        pet.chat_dialog.set_waiting(True)

    def handle_chat_message(
        self,
        user_prompt: str,
        use_drop_context: bool,
        session_id: str,
        use_conversation_context: bool,
    ) -> None:
        pet = self.pet
        pet.mark_interaction()
        if not user_prompt:
            if pet.chat_dialog is not None:
                pet.chat_dialog.set_waiting(False)
            return
        active_session = self.session_for_context_policy(user_prompt, session_id, use_conversation_context)
        set_active_session(active_session.session_id)
        self.show_user_message_for_session(user_prompt, active_session.session_id)
        if pet.config.control_enabled:
            control_plan = build_control_plan(user_prompt, pet.config.control_workspace)
            if control_plan is not None:
                self.handle_control_plan(
                    control_plan,
                    user_prompt,
                    active_session.session_id,
                    use_conversation_context,
                )
                return
        if pet.chat_dialog is not None and pet.chat_dialog.drop_context_was_removed():
            pet.last_drop_paths = []
            pet.last_drop_context = ""
        drop_context = pet.last_drop_context if use_drop_context else ""
        prompt = compose_prompt_with_drop_context(user_prompt, drop_context)
        pet.show_bubble("导师处理中。", duration=min(1.8, pet.message_duration()), action=None)
        pet.play_action(STICKER_ACTION_THINKING, loop=True)
        self.queue_agent_reply(prompt, prompt, active_session.session_id, use_conversation_context)

    def queue_agent_reply(
        self,
        prompt: str,
        memory_prompt: str,
        session_id: str,
        use_conversation_context: bool,
    ) -> None:
        pet = self.pet
        previous_task = self.active_agent_tasks.pop(session_id, None)
        if previous_task is not None and not previous_task.done():
            previous_task.cancel()
        self.active_agent_prompts[session_id] = memory_prompt
        task = pet.task_runner.run_async(
            lambda: pet.fetch_agent_reply(prompt, memory_prompt, session_id, use_conversation_context),
            on_error=lambda exc, target=session_id: self.handle_agent_task_error(target, exc),
        )
        if task is None:
            return
        self.active_agent_tasks[session_id] = task
        task.add_done_callback(lambda done_task, target=session_id: self.clear_agent_request(target, done_task))

    def clear_agent_request(self, session_id: str, task: asyncio.Task[None]) -> None:
        if self.active_agent_tasks.get(session_id) is task:
            self.active_agent_tasks.pop(session_id, None)
            self.active_agent_prompts.pop(session_id, None)

    def handle_agent_task_error(self, session_id: str, exc: Exception) -> None:
        self.active_agent_tasks.pop(session_id, None)
        self.active_agent_prompts.pop(session_id, None)
        self.pet.agent_signals.error_ready.emit(f"Agent 出错：{type(exc).__name__}: {exc}", session_id)

    def cancel_agent_request(self, session_id: str) -> None:
        pet = self.pet
        target_session_id = session_id or (pet.chat_dialog.active_session_id if pet.chat_dialog is not None else "")
        if not target_session_id:
            return
        task = self.active_agent_tasks.pop(target_session_id, None)
        user_prompt = self.active_agent_prompts.pop(target_session_id, "")
        if task is not None and not task.done():
            task.cancel()
        if user_prompt:
            reply = pet.chat_service.record_agent_request_cancelled(user_prompt, target_session_id)
        else:
            reply = "已取消本次请求。"
        if pet.chat_dialog is not None and pet.chat_dialog.active_session_id == target_session_id:
            pet.chat_dialog.add_assistant_message(reply)
            pet.chat_dialog.set_waiting(False)
            self.refresh_chat_dialog_sessions()
        pet.show_bubble(reply, duration=pet.message_duration(), action=STICKER_ACTION_TAP)

    def handle_control_plan(
        self,
        plan: ControlPlan,
        user_prompt: str,
        session_id: str,
        use_conversation_context: bool,
    ) -> None:
        pet = self.pet
        if plan.is_blocked:
            if pet.chat_dialog is not None:
                pet.chat_dialog.set_waiting(True)
            self.queue_control_reply(plan, user_prompt, session_id, use_conversation_context, False)
            return
        if plan.requires_confirmation:
            self.request_control_authorization(plan, user_prompt, session_id, use_conversation_context, False)
            return
        pet.show_bubble("执行本地只读操作。", duration=min(1.8, pet.message_duration()), action=STICKER_ACTION_THINKING)
        pet.play_action(STICKER_ACTION_THINKING, loop=True)
        self.queue_control_reply(plan, user_prompt, session_id, use_conversation_context, False)

    def request_control_authorization(
        self,
        plan: ControlPlan,
        user_prompt: str,
        session_id: str,
        use_conversation_context: bool,
        auto_continue: bool,
    ) -> None:
        pet = self.pet
        pet.pending_control_plans[plan.plan_id] = (plan, user_prompt, session_id, use_conversation_context, auto_continue)
        if pet.chat_dialog is None:
            self.open_chat()
        if pet.chat_dialog is not None:
            session = get_session(session_id) or ensure_active_session()
            pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
            if pet.chat_dialog.active_session_id != session.session_id:
                pet.chat_dialog.set_active_session(session, load_chat_history(session.session_id))
            else:
                pet.chat_dialog.set_active_session(session)
            pet.chat_dialog.add_control_plan(plan.plan_id, plan.title, plan.summary(), True)
            pet.chat_dialog.set_waiting(False)
            pet.chat_dialog.show()
            pet.chat_dialog.raise_()
            pet.chat_dialog.activate_for_input()
        pet.chat_service.record_control_plan_waiting(user_prompt, plan, session_id)
        self.refresh_chat_dialog_sessions()
        pet.show_bubble("电脑操作需要确认。", duration=pet.message_duration(), action=STICKER_ACTION_THINKING)

    def approve_control_plan(self, plan_id: str) -> None:
        pet = self.pet
        pending = pet.pending_control_plans.pop(plan_id, None)
        if pending is None:
            pet.agent_signals.error_ready.emit("电脑操作计划已过期或不存在。", "")
            return
        plan, user_prompt, session_id, use_conversation_context, auto_continue = pending
        if pet.chat_dialog is not None:
            pet.chat_dialog.set_waiting(True)
        pet.show_bubble("正在执行电脑操作。", duration=min(1.8, pet.message_duration()), action=STICKER_ACTION_THINKING)
        pet.play_action(STICKER_ACTION_THINKING, loop=True)
        self.queue_control_reply(plan, user_prompt, session_id, use_conversation_context, auto_continue)

    def cancel_control_plan(self, plan_id: str) -> None:
        pet = self.pet
        pending = pet.pending_control_plans.pop(plan_id, None)
        if pending is None:
            return
        plan, _user_prompt, session_id, _use_conversation_context, _auto_continue = pending
        reply = pet.chat_service.record_control_plan_cancelled(plan, session_id)
        pet.agent_signals.reply_ready.emit(reply, session_id)

    def queue_control_reply(
        self,
        plan: ControlPlan,
        memory_prompt: str,
        session_id: str,
        use_conversation_context: bool,
        auto_continue: bool,
    ) -> None:
        pet = self.pet
        pet.task_runner.run_async(
            lambda: self.fetch_control_reply(plan, memory_prompt, session_id, use_conversation_context, auto_continue),
            on_error=lambda exc, target=session_id: pet.agent_signals.error_ready.emit(
                f"电脑操作出错：{type(exc).__name__}: {exc}",
                target,
            ),
        )

    async def fetch_control_reply(
        self,
        plan: ControlPlan,
        memory_prompt: str,
        session_id: str,
        use_conversation_context: bool,
        auto_continue: bool,
    ) -> None:
        pet = self.pet
        result = await pet.chat_service.execute_control_plan_reply(
            plan,
            memory_prompt=memory_prompt,
            session_id=session_id,
            record_as_tool=auto_continue,
        )
        if result.ok and not auto_continue:
            pet.agent_signals.reply_ready.emit(result.text, result.session_id)
        elif not auto_continue:
            pet.agent_signals.error_ready.emit(result.text, result.session_id)
            return
        if auto_continue and result.control_result is not None:
            if pet.chat_dialog is not None and pet.chat_dialog.active_session_id == session_id:
                pet.chat_dialog.set_waiting(True)
            pet.show_bubble("继续处理下一步。", duration=min(1.8, pet.message_duration()), action=STICKER_ACTION_THINKING)
            pet.play_action(STICKER_ACTION_THINKING, loop=True)
            next_result = await pet.chat_service.continue_agent_after_control_result(
                pet.config,
                plan,
                result.control_result,
                session_id=session_id,
            )
            if next_result.control_plan is not None:
                pet.agent_signals.control_plan_ready.emit(
                    next_result.control_plan,
                    next_result.text,
                    next_result.control_source_text,
                    next_result.session_id,
                    next_result.prompt_text or memory_prompt,
                    use_conversation_context,
                )
                return
            if next_result.is_error:
                pet.agent_signals.error_ready.emit(next_result.text, next_result.session_id)
                return
            pet.agent_signals.reply_ready.emit(next_result.text, next_result.session_id)
            return

    def ask_about_dropped_files(self) -> None:
        pet = self.pet
        pet.mark_interaction()
        if not pet.last_drop_context:
            pet.show_bubble("还没有拖入文件。", duration=pet.message_duration())
            return
        user_prompt = "请先概括这些文件/文件夹的内容，再指出最值得我下一步处理的事项。"
        prompt = compose_prompt_with_drop_context(user_prompt, pet.last_drop_context)
        active_session = self.session_for_context_policy(
            user_prompt,
            ensure_active_session().session_id,
            self.context_default_enabled(),
        )
        pet.show_bubble("导师正在看文件。", duration=min(1.8, pet.message_duration()), action=None)
        pet.play_action(STICKER_ACTION_THINKING, loop=True)
        self.queue_agent_reply(prompt, prompt, active_session.session_id, self.context_default_enabled())

    def open_drop_summary(self) -> None:
        pet = self.pet
        pet.mark_interaction()
        if not pet.last_drop_context:
            pet.show_bubble("还没有拖入文件。", duration=pet.message_duration())
            return
        dialog = TextViewDialog("文件摘要", pet.last_drop_context)
        self.position_dialog_near_pet(dialog)
        dialog.activate_for_input()
        dialog.exec()

    def clear_drop_context(self) -> None:
        pet = self.pet
        pet.mark_interaction()
        pet.last_drop_paths = []
        pet.last_drop_context = ""
        pet.show_bubble("文件上下文已清除。", duration=pet.message_duration())

    def position_dialog_near_pet(self, dialog: QDialog) -> None:
        pet = self.pet
        if not isinstance(dialog, (ChatDialog, SettingsDialog)):
            dialog.adjustSize()
        size = dialog.size()
        screen = QGuiApplication.screenAt(pet.sticker_center_global()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        frame = pet.frameGeometry()
        margin = 14
        candidates = [
            QPoint(frame.left() - size.width() - margin, frame.top() + max(0, (frame.height() - size.height()) // 2)),
            QPoint(frame.right() + margin, frame.top() + max(0, (frame.height() - size.height()) // 2)),
            QPoint(frame.left() + max(0, (frame.width() - size.width()) // 2), frame.top() - size.height() - margin),
            QPoint(frame.left() + max(0, (frame.width() - size.width()) // 2), frame.bottom() + margin),
        ]
        for candidate in candidates:
            rect = QRect(candidate, size)
            if area.contains(rect):
                dialog.move(candidate)
                return
        x = min(max(candidates[0].x(), area.left() + margin), area.right() - size.width() - margin)
        y = min(max(candidates[0].y(), area.top() + margin), area.bottom() - size.height() - margin)
        dialog.move(x, y)

    def position_dialog_near_dialog(self, dialog: QDialog, anchor: QDialog) -> None:
        dialog.adjustSize()
        size = dialog.size()
        anchor_rect = anchor.frameGeometry()
        screen = QGuiApplication.screenAt(anchor_rect.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)
        margin = 14
        max_x = max(area.left() + margin, area.right() - size.width() - margin)
        max_y = max(area.top() + margin, area.bottom() - size.height() - margin)
        x = min(max(anchor_rect.center().x() - size.width() // 2, area.left() + margin), max_x)
        y = min(max(anchor_rect.center().y() - size.height() // 2, area.top() + margin), max_y)
        dialog.move(QPoint(x, y))

    def show_agent_control_request(
        self,
        plan: object,
        assistant_text: str,
        source_text: str,
        session_id: str,
        prompt_text: str,
        use_conversation_context: bool,
    ) -> None:
        pet = self.pet
        if not isinstance(plan, ControlPlan):
            pet.agent_signals.error_ready.emit("电脑操作计划格式无效。", session_id)
            return
        if assistant_text:
            pet.show_bubble("准备调用本地工具。", duration=min(1.8, pet.message_duration()), action=STICKER_ACTION_THINKING)
        elif pet.chat_dialog is not None and pet.chat_dialog.waiting_for_reply:
            pet.chat_dialog.set_waiting(False)
        if not plan.requires_confirmation and not plan.is_blocked:
            if pet.chat_dialog is None:
                self.open_chat()
            if pet.chat_dialog is not None:
                session = get_session(session_id) or ensure_active_session()
                pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
                if pet.chat_dialog.active_session_id != session.session_id:
                    pet.chat_dialog.set_active_session(session, load_chat_history(session.session_id))
                else:
                    pet.chat_dialog.set_active_session(session)
                pet.chat_dialog.add_control_plan(plan.plan_id, plan.title, plan.summary(), False)
                pet.chat_dialog.set_waiting(True)
            pet.show_bubble("执行本地只读工具。", duration=min(1.8, pet.message_duration()), action=STICKER_ACTION_THINKING)
            pet.play_action(STICKER_ACTION_THINKING, loop=True)
            self.queue_control_reply(
                plan,
                prompt_text or source_text or plan.source_text,
                session_id,
                use_conversation_context,
                True,
            )
            return
        if pet.chat_dialog is None:
            self.open_chat()
        if pet.chat_dialog is not None:
            session = get_session(session_id) or ensure_active_session()
            pet.chat_dialog.set_sessions(list_conversation_sessions(), session.session_id)
            if pet.chat_dialog.active_session_id != session.session_id:
                pet.chat_dialog.set_active_session(session, load_chat_history(session.session_id))
            else:
                pet.chat_dialog.set_active_session(session)
            pet.chat_dialog.show()
            pet.chat_dialog.raise_()
            pet.chat_dialog.activate_for_input()
        self.request_control_authorization(
            plan,
            prompt_text or source_text or plan.source_text,
            session_id,
            use_conversation_context,
            True,
        )
