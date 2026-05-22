"""Conversation and local-control service for the pet UI."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..agent.context import assemble_agent_prompt
from ..config.store import AgentConfig
from ..model_client.agent import complete_agent_response_async, local_agent_reply
from ..model_client.base import ModelClient, ModelResponse
from ..state.conversations import (
    append_chat_turn,
    create_conversation_session,
    ensure_active_session,
    get_session,
    set_active_session,
)
from ..state.agent_store import (
    TASK_STATUS_AWAITING_TOOL,
    TASK_STATUS_DONE,
    TASK_STATUS_ERROR,
    append_tool_event,
    record_memory_candidates_from_turn,
    start_task_run,
    update_task_run,
)
from ..state.memory import append_memory_turn
from ..state.user_memory import record_user_memory_turn
from ..tools.executor import execute_control_plan_async
from ..tools.registry import build_control_plan_from_model_response
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
        task = start_task_run(
            session.session_id,
            memory_prompt or prompt,
            agent_prompt=agent_prompt,
            use_context=use_conversation_context,
        )
        try:
            response = await complete_agent_response_async(
                config,
                agent_prompt,
                include_legacy_memory=bool(use_conversation_context and config.memory_enabled),
                client=self._model_client,
            )
        except Exception as exc:
            LOGGER.exception("agent reply failed")
            error_reply = f"Agent 出错：{type(exc).__name__}: {exc}"
            update_task_run(task.task_id, status=TASK_STATUS_ERROR, assistant_text=error_reply, error=str(exc))
            self._append_chat_turn(memory_prompt or prompt, error_reply, session.session_id)
            return AgentReplyResult(error_reply, session.session_id, is_error=True)

        if config.control_enabled:
            control_plan, assistant_text = self._extract_control_plan(response, config.control_workspace)
            if control_plan is not None:
                display_text = assistant_text or control_plan.summary()
                append_tool_event(
                    session.session_id,
                    event="agent_requested_control",
                    plan=control_plan,
                    task_id=task.task_id,
                    summary=control_plan.summary(),
                )
                update_task_run(task.task_id, status=TASK_STATUS_AWAITING_TOOL, assistant_text=display_text)
                if display_text:
                    self._append_chat_turn(memory_prompt or prompt, display_text, session.session_id)
                return AgentReplyResult(
                    display_text,
                    session.session_id,
                    control_plan=control_plan,
                    control_source_text=control_plan.source_text,
                )
        reply_text = str(response.content or "").strip()
        if not reply_text:
            reply_text = self._fallback_reply(memory_prompt or prompt)

        self._append_chat_turn(memory_prompt or prompt, reply_text, session.session_id)
        self._record_agent_memory_candidates(memory_prompt or prompt, reply_text, session.session_id, task.task_id)
        if use_conversation_context and getattr(config, "long_term_memory_enabled", False):
            self._record_user_memory(memory_prompt or prompt, reply_text, session.session_id)
        if use_conversation_context and config.memory_enabled:
            self._append_legacy_memory(memory_prompt or prompt, reply_text)
        update_task_run(task.task_id, status=TASK_STATUS_DONE, assistant_text=reply_text)
        return AgentReplyResult(reply_text, session.session_id)

    async def execute_control_plan_reply(
        self,
        plan: ControlPlan,
        *,
        memory_prompt: str,
        session_id: str,
    ) -> ControlExecutionReply:
        task = start_task_run(
            session_id,
            memory_prompt,
            goal=plan.title,
            use_context=False,
        )
        try:
            result = await execute_control_plan_async(plan)
            reply = result.display_text()
        except Exception as exc:
            LOGGER.exception("control execution failed")
            reply = f"电脑操作出错：{type(exc).__name__}: {exc}"
            append_tool_event(session_id, event="control_failed", plan=plan, task_id=task.task_id, summary=reply)
            update_task_run(task.task_id, status=TASK_STATUS_ERROR, assistant_text=reply, error=str(exc))
            self._append_chat_turn(memory_prompt, reply, session_id)
            return ControlExecutionReply(reply, session_id, ok=False)
        append_tool_event(session_id, event="control_executed", plan=plan, result=result, task_id=task.task_id)
        update_task_run(
            task.task_id,
            status=TASK_STATUS_DONE if result.ok else TASK_STATUS_ERROR,
            assistant_text=reply,
            error=result.error,
        )
        self._append_chat_turn(memory_prompt, reply, session_id)
        return ControlExecutionReply(reply, session_id, ok=result.ok)

    def record_control_plan_waiting(self, user_prompt: str, plan: ControlPlan, session_id: str) -> None:
        append_tool_event(session_id, event="awaiting_user_approval", plan=plan, summary=plan.summary())
        self._append_chat_turn(user_prompt, plan.summary() + "\n\n等待用户确认。", session_id)

    def record_control_plan_cancelled(self, plan: ControlPlan, session_id: str) -> str:
        reply = f"已取消电脑操作：{plan.title}"
        append_tool_event(session_id, event="control_cancelled", plan=plan, summary=reply)
        self._append_chat_turn(f"取消电脑操作：{plan.title}", reply, session_id)
        return reply

    def record_agent_request_cancelled(self, user_prompt: str, session_id: str) -> str:
        reply = "已取消本次请求。"
        self._record_agent_memory_candidates(user_prompt, reply, session_id, "")
        self._append_chat_turn(user_prompt, reply, session_id)
        return reply

    def _agent_prompt(
        self,
        config: AgentConfig,
        prompt: str,
        session_id: str,
        use_conversation_context: bool,
    ) -> str:
        return assemble_agent_prompt(
            config,
            prompt,
            session_id=session_id,
            use_conversation_context=use_conversation_context,
        )

    def _extract_control_plan(self, response: ModelResponse, workspace: str) -> tuple[ControlPlan | None, str]:
        try:
            return build_control_plan_from_model_response(response, workspace)
        except Exception:
            LOGGER.exception("failed to parse control plan from agent response")
            return None, str(response.content or "")

    def _fallback_reply(self, prompt: str) -> str:
        return local_agent_reply(str(prompt or ""))

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

    def _record_user_memory(self, prompt: str, reply: str, session_id: str) -> None:
        try:
            record_user_memory_turn(prompt, reply, session_id=session_id)
        except Exception:
            LOGGER.exception("failed to record user memory")

    def _record_agent_memory_candidates(self, prompt: str, reply: str, session_id: str, task_id: str) -> None:
        try:
            record_memory_candidates_from_turn(prompt, reply, session_id=session_id, task_id=task_id)
        except Exception:
            LOGGER.exception("failed to record agent memory candidates")
