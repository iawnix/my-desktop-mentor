"""Conversation and local-control service for the pet UI."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..agent.context import assemble_agent_prompt
from ..config.store import AgentConfig
from ..model_client.agent import (
    build_agent_messages,
    build_assistant_tool_message,
    build_tool_result_message,
    complete_agent_response_from_messages_async,
    local_agent_reply,
)
from ..model_client.base import ModelClient, ModelResponse, ToolCall
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
from ..tools.types import ControlPlan, ControlResult

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentLoopState:
    messages: list[dict[str, object]]
    tool_call: ToolCall
    assistant_content: str
    prompt_text: str
    use_conversation_context: bool


@dataclass(frozen=True)
class AgentReplyResult:
    text: str
    session_id: str
    is_error: bool = False
    control_plan: ControlPlan | None = None
    control_source_text: str = ""
    prompt_text: str = ""


@dataclass(frozen=True)
class ControlExecutionReply:
    text: str
    session_id: str
    ok: bool
    control_result: ControlResult | None = None


class PetConversationService:
    def __init__(self, model_client: ModelClient | None = None) -> None:
        self._model_client = model_client
        self._pending_agent_loops: dict[str, AgentLoopState] = {}

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
        messages = build_agent_messages(
            config,
            agent_prompt,
            include_legacy_memory=bool(use_conversation_context and config.memory_enabled),
        )
        task = start_task_run(
            session.session_id,
            memory_prompt or prompt,
            agent_prompt=agent_prompt,
            use_context=use_conversation_context,
        )
        try:
            response = await complete_agent_response_from_messages_async(config, messages, client=self._model_client)
        except Exception as exc:
            LOGGER.exception("agent reply failed")
            error_reply = f"Agent 出错：{type(exc).__name__}: {exc}"
            update_task_run(task.task_id, status=TASK_STATUS_ERROR, assistant_text=error_reply, error=str(exc))
            self._append_chat_turn(memory_prompt or prompt, error_reply, session.session_id)
            return AgentReplyResult(error_reply, session.session_id, is_error=True)

        return self._finalize_model_response(
            config,
            response,
            prompt_text=memory_prompt or prompt,
            session_id=session.session_id,
            use_conversation_context=use_conversation_context,
            task_id=task.task_id,
            messages=messages,
        )

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
            result = ControlResult(plan.plan_id, plan.title, False, "", plan.permission, error=f"{type(exc).__name__}: {exc}")
            reply = result.display_text()
            append_tool_event(session_id, event="control_failed", plan=plan, result=result, task_id=task.task_id, summary=reply)
            update_task_run(task.task_id, status=TASK_STATUS_ERROR, assistant_text=reply, error=result.error)
            self._append_chat_turn(memory_prompt, reply, session_id)
            return ControlExecutionReply(reply, session_id, ok=False, control_result=result)
        append_tool_event(session_id, event="control_executed", plan=plan, result=result, task_id=task.task_id)
        update_task_run(
            task.task_id,
            status=TASK_STATUS_DONE if result.ok else TASK_STATUS_ERROR,
            assistant_text=reply,
            error=result.error,
        )
        self._append_chat_turn(memory_prompt, reply, session_id)
        return ControlExecutionReply(reply, session_id, ok=result.ok, control_result=result)

    async def continue_agent_after_control_result(
        self,
        config: AgentConfig,
        plan: ControlPlan,
        control_result: ControlResult,
        *,
        session_id: str,
    ) -> AgentReplyResult:
        state = self._pending_agent_loops.pop(plan.plan_id, None)
        if state is None:
            LOGGER.warning("missing agent loop state for plan %s", plan.plan_id)
            return AgentReplyResult(control_result.display_text(), session_id, is_error=True)

        tool_message = build_tool_result_message(state.tool_call, control_result.display_text())
        assistant_message = build_assistant_tool_message(state.tool_call, state.assistant_content)
        messages = [*state.messages, assistant_message, tool_message]
        task = start_task_run(
            session_id,
            state.prompt_text,
            goal=state.prompt_text,
            use_context=state.use_conversation_context,
        )
        try:
            response = await complete_agent_response_from_messages_async(config, messages, client=self._model_client)
        except Exception as exc:
            LOGGER.exception("agent continuation failed")
            error_reply = f"Agent 出错：{type(exc).__name__}: {exc}"
            update_task_run(task.task_id, status=TASK_STATUS_ERROR, assistant_text=error_reply, error=str(exc))
            self._append_chat_turn(state.prompt_text, error_reply, session_id)
            return AgentReplyResult(error_reply, session_id, is_error=True)

        return self._finalize_model_response(
            config,
            response,
            prompt_text=state.prompt_text,
            session_id=session_id,
            use_conversation_context=state.use_conversation_context,
            task_id=task.task_id,
            messages=messages,
        )

    def record_control_plan_waiting(self, user_prompt: str, plan: ControlPlan, session_id: str) -> None:
        append_tool_event(session_id, event="awaiting_user_approval", plan=plan, summary=plan.summary())
        self._append_chat_turn(user_prompt, plan.summary() + "\n\n等待用户确认。", session_id)

    def record_control_plan_cancelled(self, plan: ControlPlan, session_id: str) -> str:
        self.discard_pending_agent_state(plan.plan_id)
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

    def _finalize_model_response(
        self,
        config: AgentConfig,
        response: ModelResponse,
        *,
        prompt_text: str,
        session_id: str,
        use_conversation_context: bool,
        task_id: str,
        messages: list[dict[str, object]],
    ) -> AgentReplyResult:
        if config.control_enabled:
            control_plan, assistant_text = self._extract_control_plan(response, config.control_workspace)
            if control_plan is not None:
                display_text = assistant_text or control_plan.summary()
                tool_call = response.tool_calls[0] if response.tool_calls else None
                if tool_call is not None:
                    if len(response.tool_calls or []) > 1:
                        LOGGER.warning("model returned %d tool calls; only the first one is used", len(response.tool_calls or []))
                    self._pending_agent_loops[control_plan.plan_id] = AgentLoopState(
                        messages=list(messages),
                        tool_call=tool_call,
                        assistant_content=str(response.content or ""),
                        prompt_text=prompt_text,
                        use_conversation_context=use_conversation_context,
                    )
                append_tool_event(
                    session_id,
                    event="agent_requested_control",
                    plan=control_plan,
                    task_id=task_id,
                    summary=control_plan.summary(),
                )
                update_task_run(task_id, status=TASK_STATUS_AWAITING_TOOL, assistant_text=display_text)
                if display_text:
                    self._append_chat_turn(prompt_text, display_text, session_id)
                return AgentReplyResult(
                    display_text,
                    session_id,
                    control_plan=control_plan,
                    control_source_text=control_plan.source_text,
                    prompt_text=prompt_text,
                )
        reply_text = str(response.content or "").strip()
        if not reply_text:
            reply_text = self._fallback_reply(prompt_text)

        self._append_chat_turn(prompt_text, reply_text, session_id)
        self._record_agent_memory_candidates(prompt_text, reply_text, session_id, task_id)
        if use_conversation_context and getattr(config, "long_term_memory_enabled", False):
            self._record_user_memory(prompt_text, reply_text, session_id)
        if use_conversation_context and config.memory_enabled:
            self._append_legacy_memory(prompt_text, reply_text)
        update_task_run(task_id, status=TASK_STATUS_DONE, assistant_text=reply_text)
        return AgentReplyResult(reply_text, session_id)

    def discard_pending_agent_state(self, plan_id: str) -> None:
        self._pending_agent_loops.pop(str(plan_id or ""), None)

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
