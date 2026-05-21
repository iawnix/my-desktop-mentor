from __future__ import annotations

import unittest
from types import SimpleNamespace

from desktop_mentor_app.model_client.agent import call_agent, call_agent_async, normalize_chat_url
from desktop_mentor_app.model_client.base import ModelResponse
from desktop_mentor_app.constants.model import DEFAULT_MODEL, DEFAULT_PERSONALITY_PROMPT


def agent_config(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "api_url": "",
        "api_key": "",
        "model": DEFAULT_MODEL,
        "memory_enabled": False,
        "memory_turns": 8,
        "system_prompt": DEFAULT_PERSONALITY_PROMPT,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeModelClient:
    def __init__(self, *, content: str = "ok", fail: Exception | None = None) -> None:
        self.content = content
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        self.calls.append(
            {
                "url": url,
                "api_key": api_key,
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if self.fail is not None:
            raise self.fail
        return ModelResponse(self.content)

    def complete_sync(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        self.calls.append(
            {
                "url": url,
                "api_key": api_key,
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if self.fail is not None:
            raise self.fail
        return ModelResponse(self.content)


class AgentClientTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_chat_url(self) -> None:
        self.assertEqual(normalize_chat_url(""), "")
        self.assertEqual(normalize_chat_url("http://localhost:8000/v1"), "http://localhost:8000/v1/chat/completions")
        self.assertEqual(
            normalize_chat_url("http://localhost:8000/v1/chat/completions"),
            "http://localhost:8000/v1/chat/completions",
        )
        self.assertEqual(normalize_chat_url("http://localhost:8000"), "http://localhost:8000/v1/chat/completions")

    async def test_call_agent_async_accepts_injected_model_client(self) -> None:
        config = agent_config(api_url="http://model.test/v1", api_key="token", model="mentor-model")
        client = FakeModelClient(content="model reply")

        reply = await call_agent_async(config, "hello", client=client)

        self.assertEqual(reply, "model reply")
        self.assertEqual(len(client.calls), 1)
        call = client.calls[0]
        self.assertEqual(call["url"], "http://model.test/v1/chat/completions")
        self.assertEqual(call["api_key"], "token")
        self.assertEqual(call["model"], "mentor-model")
        messages = call["messages"]
        assert isinstance(messages, list)
        self.assertEqual(messages[-1], {"role": "user", "content": "hello"})

    async def test_call_agent_async_without_url_uses_local_fallback(self) -> None:
        client = FakeModelClient(content="should not be used")

        reply = await call_agent_async(agent_config(api_url=""), "科研目标", client=client)

        self.assertIn("目标", reply)
        self.assertEqual(client.calls, [])

    async def test_call_agent_async_reports_model_errors_as_fallback(self) -> None:
        config = agent_config(api_url="http://model.test/v1")
        client = FakeModelClient(fail=TimeoutError("slow"))

        with self.assertLogs("desktop_mentor_app.model_client.agent", level="WARNING"):
            reply = await call_agent_async(config, "hello", client=client)

        self.assertIn("接口没接上", reply)
        self.assertIn("TimeoutError", reply)

    def test_call_agent_accepts_injected_sync_model_client(self) -> None:
        config = agent_config(api_url="http://model.test/v1", api_key="token", model="mentor-model")
        client = FakeModelClient(content="sync model reply")

        reply = call_agent(config, "hello", client=client)

        self.assertEqual(reply, "sync model reply")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["url"], "http://model.test/v1/chat/completions")

    def test_call_agent_reports_sync_model_errors_as_fallback(self) -> None:
        config = agent_config(api_url="http://model.test/v1")
        client = FakeModelClient(fail=TimeoutError("slow"))

        with self.assertLogs("desktop_mentor_app.model_client.agent", level="WARNING"):
            reply = call_agent(config, "hello", client=client)

        self.assertIn("接口没接上", reply)
        self.assertIn("TimeoutError", reply)


if __name__ == "__main__":
    unittest.main()
