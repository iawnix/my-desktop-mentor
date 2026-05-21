"""Compatibility exports for the agent model client.

New code should import from ``desktop_mentor_app.model_client.agent``.
"""
from __future__ import annotations

from .model_client.agent import (
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

__all__ = [
    "CONTROL_AWARENESS_PROMPT",
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
