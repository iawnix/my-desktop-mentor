"""Model client interfaces."""
from __future__ import annotations

from .agent import (
    CONTROL_AWARENESS_PROMPT,
    agent_system_prompt,
    append_memory_turn,
    build_agent_messages,
    build_assistant_tool_message,
    build_tool_result_message,
    call_agent,
    call_agent_async,
    compact_text,
    complete_agent_response,
    complete_agent_response_async,
    complete_agent_response_from_messages_async,
    limit_formatted_text,
    load_memory_messages,
    local_agent_reply,
    normalize_chat_url,
)
from .base import ModelClient, ModelResponse, SyncModelClient, ToolCall
from .openai_compatible import OpenAICompatibleModelClient

__all__ = [
    "CONTROL_AWARENESS_PROMPT",
    "ModelClient",
    "ModelResponse",
    "OpenAICompatibleModelClient",
    "SyncModelClient",
    "ToolCall",
    "agent_system_prompt",
    "append_memory_turn",
    "build_agent_messages",
    "build_assistant_tool_message",
    "build_tool_result_message",
    "call_agent",
    "call_agent_async",
    "compact_text",
    "complete_agent_response",
    "complete_agent_response_async",
    "complete_agent_response_from_messages_async",
    "limit_formatted_text",
    "load_memory_messages",
    "local_agent_reply",
    "normalize_chat_url",
]
