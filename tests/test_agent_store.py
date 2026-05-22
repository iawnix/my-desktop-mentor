from __future__ import annotations

import os
import tempfile
import unittest

from desktop_mentor_app.agent.context import assemble_agent_prompt
from desktop_mentor_app.config.store import AgentConfig, agent_store_path
from desktop_mentor_app.model_client.base import ModelResponse
from desktop_mentor_app.pet.chat_manager import PetConversationService
from desktop_mentor_app.state.agent_store import (
    MEMORY_STATUS_PENDING,
    TASK_STATUS_AWAITING_TOOL,
    TASK_STATUS_DONE,
    append_tool_event,
    build_agent_state_context,
    list_memory_candidates,
    list_recent_task_runs,
    list_recent_tool_events,
    record_memory_candidates_from_turn,
    start_task_run,
    update_task_run,
)
from desktop_mentor_app.model_client.base import ToolCall
from desktop_mentor_app.tools.types import ControlPlan, ControlResult, PermissionLevel


class AgentStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_config = os.environ.get("DESKTOP_MENTOR_CONFIG")
        os.environ["DESKTOP_MENTOR_CONFIG"] = os.path.join(self.tmpdir.name, "config.json")

    def tearDown(self) -> None:
        if self.old_config is None:
            os.environ.pop("DESKTOP_MENTOR_CONFIG", None)
        else:
            os.environ["DESKTOP_MENTOR_CONFIG"] = self.old_config
        self.tmpdir.cleanup()

    def test_task_runs_are_persisted_and_contextualized(self) -> None:
        task = start_task_run("s1", "帮我分析项目下一步", goal="分析项目下一步")
        update_task_run(task.task_id, status=TASK_STATUS_DONE, assistant_text="先补测试。")

        tasks = list_recent_task_runs("s1")
        context = build_agent_state_context("s1")

        self.assertTrue(agent_store_path().exists())
        self.assertEqual(tasks[0].task_id, task.task_id)
        self.assertEqual(tasks[0].status, TASK_STATUS_DONE)
        self.assertIn("分析项目下一步", context)
        self.assertIn("先补测试", context)

    def test_tool_events_are_available_as_evidence(self) -> None:
        plan = ControlPlan(
            "plan-1",
            "/read README.md",
            "read_file",
            "读取文件",
            ["读取 README.md"],
            {"path": "README.md"},
            PermissionLevel.READ_ONLY,
        )
        result = ControlResult("plan-1", "读取文件", True, "README content", PermissionLevel.READ_ONLY)

        event = append_tool_event("s1", event="control_executed", plan=plan, result=result)
        events = list_recent_tool_events("s1")
        context = build_agent_state_context("s1")

        self.assertIsNotNone(event)
        self.assertEqual(events[0].plan_id, "plan-1")
        self.assertTrue(events[0].ok)
        self.assertIn("最近工具证据", context)
        self.assertIn("读取文件", context)

    def test_memory_candidates_are_pending_and_secret_like_items_are_skipped(self) -> None:
        recorded = record_memory_candidates_from_turn(
            "以后默认先给结论。这个项目不要自动删除文件。api key 是 123",
            "ok",
            session_id="s1",
            task_id="t1",
        )
        candidates = list_memory_candidates(MEMORY_STATUS_PENDING)
        texts = "\n".join(candidate.text for candidate in candidates)

        self.assertEqual(len(recorded), 2)
        self.assertIn("以后默认先给结论", texts)
        self.assertIn("这个项目不要自动删除文件", texts)
        self.assertNotIn("api key", texts)

    def test_context_assembler_injects_agent_state_only_when_enabled(self) -> None:
        start_task_run("s1", "继续做桌宠", goal="桌宠会话管理")
        config = AgentConfig(memory_enabled=True, memory_turns=4)

        prompt = assemble_agent_prompt(config, "下一步", session_id="s1", use_conversation_context=True)
        plain = assemble_agent_prompt(config, "下一步", session_id="s1", use_conversation_context=False)

        self.assertIn("Agent 运行状态", prompt)
        self.assertIn("桌宠会话管理", prompt)
        self.assertEqual(plain, "下一步")


class FakeModelClient:
    def __init__(
        self,
        *,
        content: str = "记好了。",
        tool_calls: list[ToolCall] | None = None,
        responses: list[ModelResponse] | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls
        self.responses = list(responses or [])
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, object]],
        max_tokens: int,
        temperature: float,
        tools: list[dict[str, object]] | None = None,
        tool_choice: object | None = None,
    ) -> ModelResponse:
        self.calls.append(
            {
                "url": url,
                "api_key": api_key,
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        if self.responses:
            return self.responses.pop(0)
        return ModelResponse(self.content, tool_calls=self.tool_calls)


class PetConversationServiceAgentStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_config = os.environ.get("DESKTOP_MENTOR_CONFIG")
        os.environ["DESKTOP_MENTOR_CONFIG"] = os.path.join(self.tmpdir.name, "config.json")

    def tearDown(self) -> None:
        if self.old_config is None:
            os.environ.pop("DESKTOP_MENTOR_CONFIG", None)
        else:
            os.environ["DESKTOP_MENTOR_CONFIG"] = self.old_config
        self.tmpdir.cleanup()

    async def test_fetch_agent_reply_records_task_and_memory_candidates(self) -> None:
        service = PetConversationService(FakeModelClient())
        config = AgentConfig(api_url="http://model.test/v1", model="mentor-model", memory_enabled=True)

        result = await service.fetch_agent_reply(config, "以后默认先给结论。", use_conversation_context=True)

        tasks = list_recent_task_runs(result.session_id)
        candidates = list_memory_candidates(MEMORY_STATUS_PENDING)
        self.assertEqual(result.text, "记好了。")
        self.assertEqual(tasks[0].status, TASK_STATUS_DONE)
        self.assertIn("以后默认先给结论", candidates[0].text)

    async def test_fetch_agent_reply_routes_tool_call_to_control_plan(self) -> None:
        tool_call = ToolCall("tool-1", "read_file", {"path": "README.md"}, '{"path":"README.md"}')
        service = PetConversationService(FakeModelClient(content="请先授权。", tool_calls=[tool_call]))
        config = AgentConfig(api_url="http://model.test/v1", model="mentor-model", control_enabled=True)

        result = await service.fetch_agent_reply(config, "请帮我读 README", use_conversation_context=True)

        tasks = list_recent_task_runs(result.session_id)
        events = list_recent_tool_events(result.session_id)
        self.assertIsNotNone(result.control_plan)
        assert result.control_plan is not None
        self.assertEqual(result.control_plan.action, "read_file")
        self.assertTrue(result.text)
        self.assertEqual(result.prompt_text, "请帮我读 README")
        self.assertEqual(tasks[0].status, TASK_STATUS_AWAITING_TOOL)
        self.assertEqual(events[0].event, "agent_requested_control")

    async def test_tool_result_continuation_uses_tool_role_messages(self) -> None:
        tool_call = ToolCall("tool-1", "read_file", {"path": "README.md"}, '{"path":"README.md"}')
        client = FakeModelClient(
            responses=[
                ModelResponse("先读文件。", tool_calls=[tool_call]),
                ModelResponse("已基于工具结果继续处理。"),
            ]
        )
        service = PetConversationService(client)
        config = AgentConfig(api_url="http://model.test/v1", model="mentor-model", control_enabled=True)

        result = await service.fetch_agent_reply(config, "请帮我读 README", use_conversation_context=False)

        self.assertIsNotNone(result.control_plan)
        assert result.control_plan is not None
        control_result = ControlResult(
            result.control_plan.plan_id,
            result.control_plan.title,
            True,
            "README content",
            result.control_plan.permission,
        )
        follow_up = await service.continue_agent_after_control_result(
            config,
            result.control_plan,
            control_result,
            session_id=result.session_id,
        )

        self.assertEqual(follow_up.text, "已基于工具结果继续处理。")
        self.assertEqual(len(client.calls), 2)
        second_messages = client.calls[1]["messages"]
        assert isinstance(second_messages, list)
        self.assertEqual(second_messages[-2]["role"], "assistant")
        self.assertEqual(second_messages[-2]["tool_calls"][0]["id"], "tool-1")
        self.assertEqual(second_messages[-1]["role"], "tool")
        self.assertEqual(second_messages[-1]["tool_call_id"], "tool-1")
        self.assertIn("README content", second_messages[-1]["content"])


if __name__ == "__main__":
    unittest.main()
