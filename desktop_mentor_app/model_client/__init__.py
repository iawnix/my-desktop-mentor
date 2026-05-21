"""Model client interfaces."""
from __future__ import annotations

from .agent import (
    CONTROL_AWARENESS_PROMPT,
    agent_system_prompt,
    append_memory_turn,
    build_agent_messages,
    call_agent,
    call_agent_async,
    compact_text,
    limit_formatted_text,
    load_memory_messages,
    local_agent_reply,
    normalize_chat_url,
)
from .base import ModelClient, ModelResponse, SyncModelClient
from .openai_compatible import OpenAICompatibleModelClient

__all__ = [
    "CONTROL_AWARENESS_PROMPT",
    "ModelClient",
    "ModelResponse",
    "OpenAICompatibleModelClient",
    "SyncModelClient",
    "agent_system_prompt",
    "append_memory_turn",
    "build_agent_messages",
    "call_agent",
    "call_agent_async",
    "compact_text",
    "limit_formatted_text",
    "load_memory_messages",
    "local_agent_reply",
    "normalize_chat_url",
]
