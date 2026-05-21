"""Conversation and local-control service for the pet UI."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..agent_client import call_agent_async
from ..config_store import AgentConfig
from ..model_client.base import ModelClient
from ..state.conversations import (
    append_chat_turn,
    build_conversation_memory_context,
    create_conversation_session,
    ensure_active_session,
    get_session,
    set_active_session,
)
from ..state.memory import append_memory_turn
from ..tools.executor import execute_control_plan_async
from ..tools.registry import build_control_plan_from_agent_reply
from ..tools.types import ControlPlan

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentReplyResult:
    text: str
    session_id: str
    is_error: bool = False
    control_plan: ControlPlan | None = None
    control_source_text: str = ""


@dataclass(frozen=True)
class ControlExecutionReply:
    text: str
    session_id: str
    ok: bool


class PetConversationService:
    def __init__(self, model_client: ModelClient | None = None) -> None:
        self._model_client = model_client

    def session_for_context_policy(
        self,
        user_prompt: str,
        session_id: str,
        use_conversation_context: bool,
    ):
        active_session = get_session(session_id) or ensure_active_session()
        if use_conversation_context or active_session.message_count == 0:
            set_active_session(active_session.session_id)
            return active_session
        return create_conversation_session(user_prompt)

    async def fetch_agent_reply(
        self,
        config: AgentConfig,
        prompt: str,
        *,
        memory_prompt: str | None = None,
        session_id: str = "",
        use_conversation_context: bool = True,
    ) -> AgentReplyResult:
        session = get_session(session_id) or ensure_active_session()
        agent_prompt = self._agent_prompt(config, prompt, session.session_id, use_conversation_context)
        try:
            reply = await call_agent_async(
                config,
                agent_prompt,
                include_legacy_memory=bool(use_conversation_context and config.memory_enabled),
                client=self._model_client,
            )
        except Exception as exc:
            LOGGER.exception("agent reply failed")
            reply = f"Agent 出错：{type(exc).__name__}: {exc}"
            self._append_chat_turn(memory_prompt or prompt, reply, session.session_id)
            return AgentReplyResult(reply, session.session_id, is_error=True)

        if config.control_enabled:
            control_plan, cleaned_reply = self._extract_control_plan(reply, config.control_workspace)
            if control_plan is not None:
                if cleaned_reply:
                    self._append_chat_turn(memory_prompt or prompt, cleaned_reply, session.session_id)
                return AgentReplyResult(
                    cleaned_reply,
                    session.session_id,
                    control_plan=control_plan,
                    control_source_text=control_plan.source_text,
                )

        self._append_chat_turn(memory_prompt or prompt, reply, session.session_id)
        if use_conversation_context and config.memory_enabled:
            self._append_legacy_memory(memory_prompt or prompt, reply)
        return AgentReplyResult(reply, session.session_id)

    async def execute_control_plan_reply(
        self,
        plan: ControlPlan,
        *,
        memory_prompt: str,
        session_id: str,
    ) -> ControlExecutionReply:
        try:
            result = await execute_control_plan_async(plan)
            reply = result.display_text()
        except Exception as exc:
            LOGGER.exception("control execution failed")
            reply = f"电脑操作出错：{type(exc).__name__}: {exc}"
            self._append_chat_turn(memory_prompt, reply, session_id)
            return ControlExecutionReply(reply, session_id, ok=False)
        self._append_chat_turn(memory_prompt, reply, session_id)
        return ControlExecutionReply(reply, session_id, ok=result.ok)

    def record_control_plan_waiting(self, user_prompt: str, plan: ControlPlan, session_id: str) -> None:
        self._append_chat_turn(user_prompt, plan.summary() + "\n\n等待用户确认。", session_id)

    def record_control_plan_cancelled(self, plan: ControlPlan, session_id: str) -> str:
        reply = f"已取消电脑操作：{plan.title}"
        self._append_chat_turn(f"取消电脑操作：{plan.title}", reply, session_id)
        return reply

    def record_agent_request_cancelled(self, user_prompt: str, session_id: str) -> str:
        reply = "已取消本次请求。"
        self._append_chat_turn(user_prompt, reply, session_id)
        return reply

    def _agent_prompt(
        self,
        config: AgentConfig,
        prompt: str,
        session_id: str,
        use_conversation_context: bool,
    ) -> str:
        if not use_conversation_context:
            return prompt
        try:
            memory_context = build_conversation_memory_context(session_id, config.memory_turns)
        except Exception:
            LOGGER.exception("failed to build conversation memory context")
            return prompt
        if not memory_context:
            return prompt
        return f"{memory_context}\n\n当前输入:\n{prompt}"

    def _extract_control_plan(self, reply: str, workspace: str) -> tuple[ControlPlan | None, str]:
        try:
            return build_control_plan_from_agent_reply(reply, workspace)
        except Exception:
            LOGGER.exception("failed to parse control plan from agent reply")
            return None, reply

    def _append_chat_turn(self, prompt: str, reply: str, session_id: str) -> None:
        try:
            append_chat_turn(prompt, reply, session_id)
        except Exception:
            LOGGER.exception("failed to append chat turn")

    def _append_legacy_memory(self, prompt: str, reply: str) -> None:
        try:
            append_memory_turn(prompt, reply)
        except Exception:
            LOGGER.exception("failed to append legacy memory turn")
