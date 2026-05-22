"""Typed model client protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, object]
    raw_arguments: str = ""
    raw: dict[str, object] | None = None


@dataclass(frozen=True)
class ModelResponse:
    content: str
    tool_calls: list[ToolCall] | None = None
    raw: dict[str, object] | None = None


class ModelClient(Protocol):
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
        """Return a chat completion response."""


class SyncModelClient(Protocol):
    def complete_sync(
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
        """Return a chat completion response from synchronous code."""
