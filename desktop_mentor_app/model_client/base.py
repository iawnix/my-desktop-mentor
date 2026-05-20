"""Typed model client protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelResponse:
    content: str
    raw: dict[str, object] | None = None


class ModelClient(Protocol):
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
        """Return a chat completion response."""
